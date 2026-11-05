import argparse
import json
import subprocess
import sys
from pathlib import Path

from drill.engine import Campaign, campaign_path, initialize
from drill.report import dashboard
from drill.store import read_json, validate_campaign, write_json
from drill.workspace import git, repository


def current_repository(explicit):
    if explicit is not None:
        return repository(explicit)
    root = repository(Path(git(Path.cwd(), 'rev-parse', '--show-toplevel')))
    common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
    for candidate in (root, *root.parents):
        if (candidate / '.drill').is_dir():
            try:
                owner = repository(candidate)
                if Path(git(owner, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve() == common:
                    return owner
            except ValueError:
                continue
    return root


def current_revision(repo):
    try:
        root = repository(Path(git(Path.cwd(), 'rev-parse', '--show-toplevel')))
        current_common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
        selected_common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
        if current_common == selected_common:
            return git(root, 'rev-parse', '--verify', 'HEAD^{commit}')
    except ValueError:
        pass
    return git(repo, 'rev-parse', '--verify', 'HEAD^{commit}')


def current_worker(repo):
    try:
        root = repository(Path(git(Path.cwd(), 'rev-parse', '--show-toplevel')))
    except ValueError:
        return None
    if root == repo:
        return None
    for path in (repo / '.drill' / 'campaigns').glob('*/workers/*.json'):
        identity = read_json(path)
        if Path(identity['path']).resolve() == root:
            return identity
    return None


def selected_campaign(args, repo, worker):
    if args.campaign is not None:
        return args.campaign
    if worker is not None:
        return worker['campaign']
    active = repo / '.drill' / 'active.json'
    if active.is_file():
        return read_json(active)['campaign']
    if args.command == 'init':
        return 'default'
    raise ValueError('No campaign selected. Run drill init --config <file> or drill use <campaign>.')


def main(bound=None):
    parser = argparse.ArgumentParser(description='Drill runs research experiments in Git repositories.')
    commands = parser.add_subparsers(dest='command', required=True)
    names = ['init', 'baseline', 'workspace', 'step', 'resume', 'status', 'dashboard', 'run']
    if bound is None:
        names.extend(['use', 'serve', 'model'])
    for name in names:
        sub = commands.add_parser(name)
        if bound is None:
            sub.add_argument('--repo', type=Path, help='Repository root; defaults to the current repository.')
            sub.add_argument('--campaign', help='Campaign name; defaults to the selected campaign.')
        if name == 'serve':
            sub.add_argument('--port', type=int, default=8765)
        if name == 'model':
            sub.add_argument('--prompt', required=True)
        if name == 'init':
            sub.add_argument('--config', type=Path, required=True)
        if name == 'use':
            sub.add_argument('selection')
        if name in {'workspace', 'run'}:
            sub.add_argument('--worker', default='researcher')
        if name == 'step':
            source = sub.add_mutually_exclusive_group(required=bound is not None)
            source.add_argument('--worker')
            source.add_argument('--revision')
            sub.add_argument('--hypothesis', required=True)
        if name == 'resume':
            sub.add_argument('--attempt', required=True)
        if name == 'run':
            sub.add_argument('--iterations', type=int, required=True)
    args = parser.parse_args()
    try:
        if bound is None:
            repo = current_repository(args.repo)
            if args.command == 'serve':
                from drill.server import serve
                serve(repo, args.port)
                return
            if args.command == 'model':
                from drill.settings import call_model
                print(json.dumps(call_model(repo, args.prompt)))
                return
            worker = current_worker(repo)
            name = args.selection if args.command == 'use' else selected_campaign(args, repo, worker)
            path = campaign_path(repo, name)
        else:
            path = bound
        if args.command == 'init':
            if bound is not None:
                raise ValueError('A pinned launcher cannot initialize or upgrade campaigns.')
            result = initialize(repo, name, args.config)
            write_json(repo / '.drill' / 'active.json', {'campaign': name})
        elif args.command == 'use':
            Campaign(path)
            write_json(repo / '.drill' / 'active.json', {'campaign': name})
            result = {'campaign': name, 'repo': str(repo)}
        else:
            if bound is None:
                validate_campaign(path)
                if args.command == 'run' and not ({'agent', 'research'} & read_json(path / 'config.json').keys()):
                    print(json.dumps(Campaign(path).run(args.worker, args.iterations), indent=2, sort_keys=True))
                    return
                if args.command == 'step' and args.worker is None and args.revision is None:
                    if worker is not None and worker['campaign'] == name:
                        args.worker = worker['worker']
                    else:
                        args.revision = current_revision(repo)
                process = subprocess.run([sys.executable, '-B', str(path / 'hub.py'), args.command, *forwarded(args)])
                raise SystemExit(process.returncode)
            campaign = Campaign(path)
            if args.command == 'baseline':
                result = campaign.evaluate('baseline')
            elif args.command == 'step':
                result = campaign.evaluate('candidate', ref=args.revision, worker=args.worker, hypothesis=args.hypothesis)
            elif args.command == 'workspace':
                result = campaign.workspace(args.worker)
            elif args.command == 'resume':
                result = campaign.resume(args.attempt)
            elif args.command == 'run':
                result = campaign.run(args.worker, args.iterations)
            elif args.command == 'dashboard':
                result = dashboard(campaign)
            else:
                result = campaign.status()
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        raise SystemExit(2) from exc


def forwarded(args):
    result = []
    for key in ('worker', 'revision', 'hypothesis', 'attempt', 'iterations'):
        value = getattr(args, key, None)
        if value is not None:
            result.extend(['--' + key, str(value)])
    return result
