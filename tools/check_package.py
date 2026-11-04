import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('wheel', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with zipfile.ZipFile(args.wheel) as archive:
        names = archive.namelist()
        if not any(name.endswith('/LICENSE') for name in names) or not any(name.endswith('/NOTICE') for name in names):
            raise RuntimeError('The wheel must include LICENSE and NOTICE.')
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary).resolve()
        installed = base / 'installed'
        process = subprocess.run([sys.executable, '-m', 'pip', '--disable-pip-version-check', 'install', '--no-index', '--no-deps', '--target', str(installed), str(args.wheel.resolve())], capture_output=True, text=True)
        if process.returncode:
            raise RuntimeError(process.stdout + process.stderr)
        repo = base / 'project'
        repo.mkdir()
        shutil.copy2(root / 'examples/toy/parameters.json', repo / 'parameters.json')
        for arguments in [('init', '-q'), ('config', 'user.email', 'package@example.invalid'), ('config', 'user.name', 'Drill Package Check'), ('add', 'parameters.json'), ('commit', '-qm', 'Start the package check')]:
            subprocess.run(['git', '-C', str(repo), *arguments], check=True, capture_output=True)
        environment = dict(os.environ, PYTHONPATH=str(installed), PYTHONDONTWRITEBYTECODE='1')
        command = installed / 'bin' / 'drill'
        def drill(action, *arguments):
            output = subprocess.check_output([str(command), action, *arguments], cwd=repo, env=environment, text=True)
            return json.loads(output)
        drill('init', '--config', str(root / 'examples/toy/hub.json'))
        baseline = drill('baseline')
        experiments = drill('run', '--iterations', '5')
        status = drill('status')
        report = drill('dashboard')
        expected = repo / '.worktrees/drill/default/researcher'
        if baseline['score'] != 25 or status['incumbent']['score'] != 0 or len(experiments['attempts']) != 5 or Path(experiments['worker']['path']) != expected:
            raise RuntimeError('The installed command did not complete its research loop.')
        if 'aria-label="Drill"' not in Path(report['path']).read_text():
            raise RuntimeError('The generated report is missing the Drill logo.')
        launcher = repo / '.drill/campaigns/default/hub.py'
        pinned = json.loads(subprocess.check_output([sys.executable, '-I', str(launcher), 'status'], cwd=base, text=True))
        if pinned['incumbent']['score'] != 0:
            raise RuntimeError('The saved launcher did not work independently.')
        print(json.dumps({'verdict': 'VERIFIED', 'license_files_included': True, 'installed_command': True, 'default_selection': True, 'baseline': 25, 'final': 0, 'iterations': 5, 'owned_worker_location': True, 'independent_saved_launcher': True}, sort_keys=True))


if __name__ == '__main__':
    main()
