import hashlib
import io
import os
import posixpath
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urljoin


POINTER_VERSION = b'version https://git-lfs.github.com/spec/v1'


def command(repo, *arguments, check=True):
    try:
        result = subprocess.run(['git', '-C', str(repo), *arguments], capture_output=True, stdin=subprocess.DEVNULL, env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_LFS_SKIP_SMUDGE='1'), timeout=300)
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Git materialization timed out.') from exc
    if check and result.returncode:
        raise ValueError(result.stderr.decode(errors='replace').strip() or 'Git materialization failed.')
    return result


def extract(repo, commit, destination):
    destination.mkdir(parents=True, exist_ok=True)
    data = command(repo, 'archive', '--format=tar', commit).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as source:
        for member in source.getmembers():
            target = destination / member.name
            if not target.resolve().is_relative_to(destination.resolve()) or member.islnk() or not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError('Source snapshots require files, directories, and contained symlinks.')
            if member.issym() and not (target.parent / member.linkname).resolve().is_relative_to(destination.resolve()):
                raise ValueError('Source symlink escapes the committed snapshot.')
        source.extractall(destination, filter='data')


def module_configuration(repo, commit):
    result = command(repo, 'config', '-z', '--blob', f'{commit}:.gitmodules', '--get-regexp', r'^submodule\..*\.path$', check=False)
    entries = {}
    for entry in result.stdout.decode().split('\0'):
        if not entry:
            continue
        key, path = entry.split('\n', 1)
        name = key[len('submodule.'):-len('.path')]
        if Path(name).is_absolute() or any(part in {'.', '..', '.git'} for part in Path(name).parts):
            raise ValueError('Submodule registration name is unsafe.')
        url = command(repo, 'config', '--blob', f'{commit}:.gitmodules', '--get', f'submodule.{name}.url', check=False).stdout.decode().strip()
        entries[path] = (name, url)
    return entries


def module_url(repo, url):
    if not url.startswith(('./', '../')):
        return url
    origin = command(repo, 'remote', 'get-url', 'origin', check=False).stdout.decode().strip() or str(repo.resolve())
    if '://' in origin:
        return urljoin(origin.rstrip('/') + '/', url)
    if re.match(r'^[^/]+:', origin):
        host, path = origin.split(':', 1)
        return host + ':' + posixpath.normpath(posixpath.join(path, url))
    base = Path(origin) if Path(origin).is_absolute() else repo / origin
    return str((base / url).resolve())


def object_present(repo, commit):
    return repo.is_dir() and command(repo, 'cat-file', '-e', f'{commit}^{{commit}}', check=False).returncode == 0


def local_module(repo, name, relative, commit):
    common = Path(command(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir').stdout.decode().strip())
    for candidate in (common / 'modules' / name, repo / relative):
        if object_present(candidate, commit):
            return candidate
    return None


def pointer(path):
    if path.is_symlink() or not path.is_file():
        return None
    with path.open('rb') as handle:
        data = handle.read(1025)
    if not data.startswith(POINTER_VERSION):
        return None
    match = re.fullmatch(rb'version https://git-lfs.github.com/spec/v1\r?\noid sha256:([0-9a-f]{64})\r?\nsize ([0-9]+)\r?\n?', data)
    if match is None:
        raise ValueError(f'Unsupported or malformed Git LFS pointer: {path.name}')
    return match[1].decode(), int(match[2])


def lfs_object(repo, oid):
    common = Path(command(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir').stdout.decode().strip())
    storage = command(repo, 'config', '--path', '--get', 'lfs.storage', check=False).stdout.decode().strip()
    root = Path(storage) if storage else common / 'lfs'
    if not root.is_absolute():
        root = common / root
    path = root / 'objects' / oid[:2] / oid[2:4] / oid
    return path if path.is_file() and not path.is_symlink() else None


def verified_copy(source, destination, oid, size):
    if source.stat().st_size != size:
        raise ValueError('Git LFS object size does not match its committed pointer.')
    with source.open('rb') as handle:
        if hashlib.file_digest(handle, 'sha256').hexdigest() != oid:
            raise ValueError('Git LFS object hash does not match its committed pointer.')
    shutil.copyfile(source, destination)
    with destination.open('rb') as handle:
        if hashlib.file_digest(handle, 'sha256').hexdigest() != oid:
            raise ValueError('Git LFS object changed while copying into the snapshot.')


def fetch_lfs(repo, commit, oid, temporary):
    origin = command(repo, 'remote', 'get-url', 'origin', check=False).stdout.decode().strip()
    if not origin:
        raise ValueError('Git LFS fetch needs a configured origin remote.')
    if '://' not in origin and not re.match(r'^[^/]+:', origin) and not Path(origin).is_absolute():
        origin = str((repo / origin).resolve())
    clone = temporary / 'lfs-source'
    command(repo, 'clone', '--shared', '--no-checkout', '--', str(repo), str(clone))
    command(clone, 'remote', 'set-url', 'origin', origin)
    command(clone, 'config', 'lfs.storage', str(temporary / 'lfs-cache'))
    if command(clone, 'lfs', 'version', check=False).returncode:
        raise ValueError('Git LFS must be installed for explicitly allowed downloads.')
    command(clone, 'lfs', 'fetch', 'origin', commit)
    result = lfs_object(clone, oid)
    if result is None:
        raise ValueError('Git LFS did not provide the requested object.')
    return result


def snapshot(repo, commit, destination, settings, prefix=Path(), depth=0):
    if depth > 32:
        raise ValueError('Submodule nesting exceeds the supported depth.')
    extract(repo, commit, destination)
    entries = command(repo, 'ls-tree', '-rz', commit).stdout.split(b'\0')
    modules = []
    for entry in entries:
        if not entry:
            continue
        metadata, relative = entry.split(b'\t', 1)
        mode, _, oid = metadata.decode().split()
        if mode == '160000':
            modules.append((relative.decode(), oid))
    if modules and not settings['submodules']:
        raise ValueError('Enable materialization.submodules to include committed submodule contents.')
    inventory = []
    configurations = module_configuration(repo, commit) if modules else {}
    for relative, oid in modules:
        target = destination / relative
        if not target.resolve().is_relative_to(destination.resolve()) or target.is_symlink():
            raise ValueError('Submodule path escapes the source snapshot.')
        if relative not in configurations:
            raise ValueError('Submodule has no matching committed registration.')
        name, url = configurations[relative]
        source = local_module(repo, name, relative, oid)
        with tempfile.TemporaryDirectory(prefix='.drill-materialize-', dir=destination.parent) as scratch:
            if source is None:
                if not settings['allow_network']:
                    raise ValueError(f'Submodule commit is unavailable locally: {relative}. Downloads are disabled.')
                if not url:
                    raise ValueError('Submodule downloads require a committed URL.')
                url = module_url(repo, url)
                source = Path(scratch) / 'module'
                source.mkdir()
                command(source, 'init', '--bare', '-q')
                command(source, 'remote', 'add', 'origin', url)
                command(source, 'fetch', '--no-tags', '--depth=1', '--', url, oid)
            inventory.append({'kind': 'submodule', 'path': str(prefix / relative), 'commit': oid})
            inventory.extend(snapshot(source, oid, target, settings, prefix / relative, depth + 1))
    for path in sorted(destination.rglob('*')):
        if any(path == destination / relative or (destination / relative) in path.parents for relative, oid in modules):
            continue
        identity = pointer(path)
        if identity is None:
            continue
        if not settings['lfs']:
            raise ValueError('Enable materialization.lfs to replace Git LFS pointers with verified data.')
        oid, size = identity
        source = lfs_object(repo, oid)
        with tempfile.TemporaryDirectory(prefix='.drill-materialize-', dir=destination.parent) as scratch:
            if source is None:
                if not settings['allow_network']:
                    raise ValueError(f'Git LFS object is unavailable locally: {path.relative_to(destination)}. Downloads are disabled.')
                source = fetch_lfs(repo, commit, oid, Path(scratch))
            verified_copy(source, path, oid, size)
        inventory.append({'kind': 'lfs', 'path': str(prefix / path.relative_to(destination)), 'sha256': oid, 'size': size})
    return inventory


def archive(repo, commit, destination, materialization=None):
    settings = {'submodules': False, 'lfs': False, 'allow_network': False, **(materialization or {})}
    if destination.exists():
        raise ValueError('Source snapshot destination already exists.')
    return snapshot(repo, commit, destination, settings)
