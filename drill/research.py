from pathlib import Path

from drill.model import relative_path
from drill.workspace import git, worker_revision
from drill.store import read_json, records


def validate_research(value):
    fields = {'brief', 'editable_paths', 'max_iterations', 'budget_seconds'}
    if not isinstance(value, dict) or set(value) - fields:
        raise ValueError('Research accepts a brief, editable_paths, max_iterations, and budget_seconds.')
    brief = value.get('brief')
    if not isinstance(brief, str) or not brief.strip():
        raise ValueError('Research requires a nonempty human-owned brief.')
    paths = value.get('editable_paths')
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) for p in paths) or len(set(paths)) != len(paths):
        raise ValueError('Research requires unique exact editable file paths.')
    for name in paths:
        path = relative_path(name)
        if not path.parts or path.as_posix() != name or path.parts[0] in {'.drill', '.worktrees'} or any(ord(c) < 32 for c in name):
            raise ValueError('Editable files require exact canonical paths without control characters.')
    limit = value.get('max_iterations', 5)
    budget = value.get('budget_seconds', 300)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Research max_iterations must be between 1 and 100.')
    if type(budget) not in (int, float) or not 0 < budget <= 86400:
        raise ValueError('Research budget_seconds must be positive and at most one day.')
    return {'brief': brief.strip(), 'editable_paths': paths, 'max_iterations': limit, 'budget_seconds': budget}


def mode_at(repo, commit, name):
    entry = git(repo, '--literal-pathspecs', 'ls-tree', '-z', commit, '--', name, binary=True)
    return entry.split(b' ', 1)[0].decode() if entry else None


def validate_inputs(repo, initial, config, config_path):
    research = config.get('research')
    if research is None:
        return
    protected = set(config['evaluator']['assets'])
    for path in [config_path, *((config_path.parent / config[role]['adapter']).resolve() for role in ('evaluator', 'agent') if role in config)]:
        if path.is_relative_to(repo):
            protected.add(path.relative_to(repo).as_posix())
    for name in research['editable_paths']:
        if name in protected:
            raise ValueError(f'An editable file is a frozen evaluator or configuration input: {name}')
        for path in [Path(name), *Path(name).parents]:
            if str(path) == '.':
                continue
            mode = mode_at(repo, initial, path.as_posix())
            allowed = {None, '100644', '100755'} if path == Path(name) else {None, '040000'}
            if mode not in allowed:
                raise ValueError(f'Editable paths must identify regular source files: {name}')


def validate_candidate(repo, initial, commit, research):
    changed = git(repo, 'diff', '--name-only', '--no-renames', '-z', initial, commit, binary=True).decode().split('\0')
    for name in filter(None, changed):
        if name not in research['editable_paths']:
            raise ValueError(f'Candidate changed a file outside the research scope: {name!r}')
        if mode_at(repo, commit, name) not in {None, '100644', '100755'}:
            raise ValueError(f'Research candidate is not a regular source file: {name!r}')


def prepare_worker(campaign, worker, reference):
    if any(row.get('worker') == worker and row['verdict'] in {'RUNNING', 'PENDING'} for row in records(campaign.path)):
        raise ValueError('This worker has an incomplete evaluation. Inspect or resume it before continuing.')
    for request in (campaign.path / 'agent-runs').glob('*/request.json'):
        if not (request.parent / 'outcome.json').exists() and read_json(request)['worker']['worker'] == worker:
            raise ValueError('This worker has an interrupted agent run. Inspect its retained request and checkout before using a different named worker.')
    current = worker_revision(campaign.path, campaign.manifest, campaign.config, worker)
    identity = campaign.workspace(worker)
    path = Path(identity['path'])
    target_tree = git(campaign.repo, 'rev-parse', f'{reference["source_commit"]}^{{tree}}')
    if git(path, 'rev-parse', 'HEAD^{tree}') == target_tree:
        return current
    checkpoint = git(path, '-c', 'commit.gpgsign=false', 'commit-tree', target_tree, '-p', current, '-m', 'Start the next research experiment from the accepted result')
    git(path, '-c', 'core.hooksPath=/dev/null', '-c', 'merge.autostash=false', 'merge', '--ff-only', '--no-edit', '--no-overwrite-ignore', checkpoint)
    if worker_revision(campaign.path, campaign.manifest, campaign.config, worker) != checkpoint:
        raise ValueError('Worker changed while preparing the next experiment.')
    return checkpoint
