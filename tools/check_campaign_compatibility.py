import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def invoke(tool, command, *arguments, cwd):
    output = subprocess.check_output([sys.executable, '-B', str(tool / 'hub.py'), command, *arguments], cwd=cwd, text=True)
    return json.loads(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--previous', type=Path, required=True)
    args = parser.parse_args()
    current = Path(__file__).resolve().parents[1]
    previous = args.previous.resolve()
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary) / 'project'
        subprocess.run([sys.executable, '-B', str(previous / 'examples/toy/demo.py'), str(repo)], check=True, capture_output=True, text=True)
        campaign = repo / '.drill/campaigns/demo'
        manifest = json.loads((campaign / 'manifest.json').read_text())
        names = [*manifest['frozen_files'], 'manifest.json', 'runtime.json']
        before = {name: hashlib.sha256((campaign / name).read_bytes()).hexdigest() for name in names}
        saved_runtime = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (campaign / '.runtime/drill').glob('*.py')}
        current_runtime = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (current / 'drill').glob('*.py')}
        if saved_runtime == current_runtime:
            raise RuntimeError('Provide a previous version with a different saved runtime.')
        invoke(current, 'use', 'demo', '--repo', str(repo), cwd=repo)
        selected = invoke(current, 'status', cwd=repo)
        worker = repo / '.worktrees/drill/demo/researcher'
        result = invoke(current, 'step', '--hypothesis', 'Check an existing worker through the new command defaults.', cwd=worker)
        after = {name: hashlib.sha256((campaign / name).read_bytes()).hexdigest() for name in names}
        if before != after or selected['incumbent']['score'] != 0 or result['verdict'] != 'REJECTED' or result['worker'] != 'researcher':
            raise RuntimeError('Existing campaign behavior changed.')
        config = json.loads((current / 'examples/toy/hub.json').read_text())
        config['schema_version'] = 3
        config.pop('agent')
        config['evaluator']['adapter'] = str(current / 'examples/toy/evaluator.py')
        config['evaluator']['source_paths'] = ['parameters.json']
        config['research'] = {'brief': 'Check explicit versioned research setup.', 'editable_paths': ['parameters.json'], 'max_iterations': 1, 'budget_seconds': 10}
        config_path = Path(temporary) / 'research.json'
        config_path.write_text(json.dumps(config))
        legacy = subprocess.run([sys.executable, '-B', str(previous / 'hub.py'), 'init', '--repo', str(repo), '--campaign', 'research', '--config', str(config_path)], capture_output=True, text=True)
        if legacy.returncode == 0 or 'schema' not in legacy.stderr.lower() or (repo / '.drill/campaigns/research').exists():
            raise RuntimeError('The previous client did not refuse the new research configuration.')
        invoke(current, 'init', '--repo', str(repo), '--campaign', 'research', '--config', str(config_path), cwd=repo)
        if before != {name: hashlib.sha256((campaign / name).read_bytes()).hexdigest() for name in names}:
            raise RuntimeError('Creating a research campaign changed the saved previous campaign.')
        print(json.dumps({'old_client_rejects_source_selection_schema': True, 'new_client_accepts_source_selection_schema': True, 'verdict': 'VERIFIED', 'different_runtime_versions': True, 'protected_files_unchanged': len(before), 'existing_best_score': 0, 'worker_selected_without_flags': True, 'existing_launcher_handled_candidate': True}, sort_keys=True))


if __name__ == '__main__':
    main()
