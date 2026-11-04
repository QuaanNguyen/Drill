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
        saved_cli = (campaign / '.runtime/drill/cli.py').read_bytes()
        if saved_cli == (current / 'drill/cli.py').read_bytes():
            raise RuntimeError('Provide a previous version with a different command implementation.')
        invoke(current, 'use', 'demo', '--repo', str(repo), cwd=repo)
        selected = invoke(current, 'status', cwd=repo)
        worker = repo / '.worktrees/drill/demo/researcher'
        result = invoke(current, 'step', '--hypothesis', 'Check an existing worker through the new command defaults.', cwd=worker)
        after = {name: hashlib.sha256((campaign / name).read_bytes()).hexdigest() for name in names}
        if before != after or selected['incumbent']['score'] != 0 or result['verdict'] != 'REJECTED' or result['worker'] != 'researcher':
            raise RuntimeError('Existing campaign behavior changed.')
        print(json.dumps({'verdict': 'VERIFIED', 'different_command_versions': True, 'protected_files_unchanged': len(before), 'existing_best_score': 0, 'worker_selected_without_flags': True, 'existing_launcher_handled_candidate': True}, sort_keys=True))


if __name__ == '__main__':
    main()
