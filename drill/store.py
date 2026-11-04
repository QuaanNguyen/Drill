import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f'Nonfinite JSON constant: {token}')))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix=f'.{path.name}-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('This campaign or workspace is busy. Use a different worker or retry after it finishes.') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(f'Frozen input symlink escapes its root: {path}')
            result[str(path.relative_to(root))] = 'symlink:' + str(path.readlink())
        elif path.is_file():
            result[str(path.relative_to(root))] = digest(path)
    return result


def package_inventory(root):
    return {str(path.relative_to(root)): digest(path) for path in sorted(root.rglob('*.py'))}


def validate_campaign(campaign):
    manifest = read_json(campaign / 'manifest.json')
    files = manifest['frozen_files']
    actual = {name: digest(campaign / name) for name in ('config.json', 'hub.py', 'AGENTS.md', 'agents.json')}
    actual.update({'.runtime/' + key: value for key, value in package_inventory(campaign / '.runtime').items()})
    actual.update({'evaluation/' + key: value for key, value in inventory(campaign / 'evaluation').items()})
    if actual != files:
        raise ValueError('Frozen campaign runtime, configuration, or evaluator changed. Restore it or create a new campaign.')
    return manifest


def records(campaign):
    result = []
    for directory in sorted((campaign / 'attempts').glob('[0-9]' * 6)):
        path = directory / 'record.json'
        if not path.exists():
            continue
        record = read_json(path)
        seal = directory / 'seal.json'
        if record['verdict'] != 'RUNNING':
            source_hashes = directory / 'source-hashes.json'
            missing_source = not source_hashes.is_file() and record['verdict'] in {'BASELINE', 'ACCEPTED', 'REJECTED'}
            changed_source = source_hashes.is_file() and inventory(directory / 'source') != read_json(source_hashes)
            if not seal.exists() or read_json(seal) != receipt_inventory(directory) or missing_source or changed_source:
                record = dict(record, verdict='INVALID', score=None, metrics={}, reason='Saved experiment evidence changed.')
        result.append(record)
    valid_references = {row['attempt_id'] for row in result if row['verdict'] == 'BASELINE'}
    while True:
        expanded = valid_references | {row['attempt_id'] for row in result if row['verdict'] == 'ACCEPTED' and row.get('promotion_reference') in valid_references}
        if expanded == valid_references:
            break
        valid_references = expanded
    return [dict(row, verdict='INVALID', score=None, metrics={}, reason='The accepted reference evidence is no longer intact.') if row['verdict'] == 'ACCEPTED' and row['attempt_id'] not in valid_references else row for row in result]


def receipt_inventory(directory):
    files = {str(path.relative_to(directory)): digest(path) for path in directory.rglob('*') if path.is_file() and path.name != 'seal.json' and path.relative_to(directory).parts[0] != 'source'}
    return files


def save_record(directory, record):
    write_json(directory / 'record.json', record)
    if record['verdict'] != 'RUNNING':
        write_json(directory / 'seal.json', receipt_inventory(directory))


def incumbent(campaign):
    available = [row for row in records(campaign) if row['verdict'] in {'BASELINE', 'ACCEPTED'}]
    direction = read_json(campaign / 'config.json')['objective']['direction']
    return (max(available, key=lambda row: row['score']) if direction == 'maximize' else min(available, key=lambda row: row['score'])) if available else None
