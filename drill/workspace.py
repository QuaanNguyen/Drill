import io
import subprocess
import tarfile
from pathlib import Path

from drill.model import identifier, relative_path
from drill.store import lock, read_json, write_json


def git(repo, *args, binary=False):
    process = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if process.returncode:
        raise ValueError(process.stderr.decode(errors='replace').strip() or 'Git operation failed.')
    return process.stdout if binary else process.stdout.decode().strip()


def repository(path):
    path = path.resolve()
    if Path(git(path, 'rev-parse', '--show-toplevel')).resolve() != path:
        raise ValueError('Repository path must be its Git working tree root.')
    return path


def revision(repo, ref):
    return git(repo, 'rev-parse', '--verify', '--end-of-options', f'{ref}^{{commit}}')


def contained(repo, relative):
    path = repo / relative_path(relative)
    if not path.resolve().is_relative_to(repo.resolve()):
        raise ValueError('Workspace path escapes the repository through a symlink.')
    for parent in [path, *path.parents]:
        if parent == repo:
            break
        if parent.is_symlink():
            raise ValueError('Managed directories cannot use symlinks.')
    return path


def ignore_local(repo, paths):
    exclude = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude'))
    exclude.parent.mkdir(parents=True, exist_ok=True)
    text = exclude.read_text() if exclude.exists() else ''
    missing = ['/' + value.rstrip('/') + '/' for value in paths if '/' + value.rstrip('/') + '/' not in text.splitlines()]
    if missing:
        exclude.write_text(text.rstrip() + '\n' + '\n'.join(missing) + '\n')


def archive(repo, commit, destination):
    destination.mkdir()
    data = git(repo, 'archive', '--format=tar', commit, binary=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as source:
        for member in source.getmembers():
            target = destination / member.name
            if not target.resolve().is_relative_to(destination.resolve()) or member.islnk() or not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError('Source snapshots require files, directories, and contained symlinks.')
            if member.issym() and not (target.parent / member.linkname).resolve().is_relative_to(destination.resolve()):
                raise ValueError('Source symlink escapes the committed snapshot.')
        source.extractall(destination, filter='data')
    modules = git(repo, 'ls-tree', '-r', commit)
    if any(line.startswith('160000 ') for line in modules.splitlines()):
        raise ValueError('Git submodules require an explicit external artifact adapter and are unsupported in source snapshots.')


def registration(repo):
    entries = git(repo, 'worktree', 'list', '--porcelain').split('\n\n')
    return {Path(lines[0][9:]).resolve(): dict(line.split(' ', 1) if ' ' in line else (line, '') for line in lines[1:]) for entry in entries if (lines := entry.splitlines())}


def get_workspace(campaign, manifest, config, worker, create=False, start=None):
    identifier(worker)
    repo = Path(manifest['repo'])
    root = config['workspace']['root']
    path = contained(repo, f'{root}/{manifest["campaign"]}/{worker}')
    branch = f'drill/{manifest["campaign"]}/{worker}'
    owner_path = campaign / 'workers' / f'{worker}.json'
    identity = {'path': str(path), 'branch': branch, 'worker': worker, 'campaign': manifest['campaign'], 'repo': str(repo), 'instructions': str(campaign / 'AGENTS.md'), 'agent_policy': str(campaign / 'agents.json')}
    with lock(repo / '.drill' / '.workspace.lock'):
        registered = registration(repo)
        if owner_path.exists():
            if read_json(owner_path) != identity or not path.is_dir() or registered.get(path.resolve(), {}).get('branch') != f'refs/heads/{branch}':
                raise ValueError('Worker ownership or Git registration changed. No files were reset or removed.')
            return identity
        if not create:
            raise ValueError('Unknown worker. Create its managed workspace first.')
        if path.exists() or path.resolve() in registered:
            raise ValueError('Worker destination is already occupied. Choose another worker name.')
        if subprocess.run(['git', '-C', str(repo), 'show-ref', '--verify', '--quiet', f'refs/heads/{branch}']).returncode == 0:
            raise ValueError('Worker branch already exists. Choose another worker name.')
        path.parent.mkdir(parents=True, exist_ok=True)
        git(repo, 'worktree', 'add', '-b', branch, str(path), start or manifest['initial_revision'])
        write_json(owner_path, identity)
        return identity


def worker_revision(campaign, manifest, config, worker):
    identity = get_workspace(campaign, manifest, config, worker)
    path = Path(identity['path'])
    if git(path, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Worker checkout is dirty. Commit its source changes before evaluation.')
    return revision(path, 'HEAD')
