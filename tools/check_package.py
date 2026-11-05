import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
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
        venv.EnvBuilder(with_pip=True).create(installed)
        interpreter = installed / 'bin' / 'python'
        process = subprocess.run([str(interpreter), '-m', 'pip', '--disable-pip-version-check', 'install', '--no-index', '--no-deps', str(args.wheel.resolve())], capture_output=True, text=True)
        if process.returncode:
            raise RuntimeError(process.stdout + process.stderr)
        fixtures = base / 'fixtures'
        fixtures.mkdir()
        for name in ('parameters.json', 'hub.json', 'evaluator.py', 'agent.py'):
            shutil.copy2(root / 'examples/toy' / name, fixtures / name)
        repo = base / 'project'
        repo.mkdir()
        shutil.copy2(fixtures / 'parameters.json', repo / 'parameters.json')
        for arguments in [('init', '-q'), ('config', 'user.email', 'package@example.invalid'), ('config', 'user.name', 'Drill Package Check'), ('add', 'parameters.json'), ('commit', '-qm', 'Start the package check')]:
            subprocess.run(['git', '-C', str(repo), *arguments], check=True, capture_output=True)
        environment = {key: value for key, value in os.environ.items() if key not in {'PYTHONPATH', 'PYTHONHOME'}}
        environment['PYTHONDONTWRITEBYTECODE'] = '1'
        command = installed / 'bin' / 'drill'
        def drill(action, *arguments, cwd=None):
            output = subprocess.check_output([str(command), action, *arguments], cwd=cwd or repo, env=environment, text=True)
            return json.loads(output)
        drill('init', '--config', str(fixtures / 'hub.json'))
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
        second = base / 'another-project'
        second.mkdir()
        shutil.copy2(fixtures / 'parameters.json', second / 'parameters.json')
        shutil.copy2(fixtures / 'evaluator.py', second / 'evaluator.py')
        config = json.loads((fixtures / 'hub.json').read_text())
        del config['agent']
        config['schema_version'] = 2
        config['research'] = {'brief': 'Improve the integer parameter.', 'editable_paths': ['parameters.json'], 'max_iterations': 2, 'budget_seconds': 10}
        (second / 'research.json').write_text(json.dumps(config))
        for arguments in [('init', '-q'), ('config', 'user.email', 'package@example.invalid'), ('config', 'user.name', 'Drill Package Check'), ('add', '.'), ('commit', '-qm', 'Start independent research')]:
            subprocess.run(['git', '-C', str(second), *arguments], check=True, capture_output=True)
        drill('init', '--config', 'research.json', cwd=second)
        drill('baseline', cwd=second)
        handoff = drill('run', '--iterations', '2', cwd=second)
        if handoff['mode'] != 'current_agent' or handoff['research'] != config['research']:
            raise RuntimeError('The installed command did not hand research to the current assistant.')
        worker = Path(handoff['worker']['path'])
        (worker / 'parameters.json').write_text(json.dumps({'value': 3}))
        for arguments in [('add', 'parameters.json'), ('commit', '-qm', 'Improve the parameter')]:
            subprocess.run(['git', '-C', str(worker), *arguments], check=True, capture_output=True)
        candidate = drill('step', '--hypothesis', 'Moving toward seven reduces error.', cwd=worker)
        if candidate['verdict'] != 'ACCEPTED' or drill('status', cwd=worker)['incumbent']['score'] != 16:
            raise RuntimeError('The installed command did not evaluate the current assistant worker.')
        if drill('status')['incumbent']['score'] != 0:
            raise RuntimeError('Research in the second repository changed the first campaign.')
        print(json.dumps({'verdict': 'VERIFIED', 'license_files_included': True, 'installed_command': True, 'independent_repositories': True, 'current_agent_handoff': True, 'worker_command_discovery': True, 'default_selection': True, 'baseline': 25, 'final': 0, 'iterations': 5, 'owned_worker_location': True, 'independent_saved_launcher': True}, sort_keys=True))


if __name__ == '__main__':
    main()
