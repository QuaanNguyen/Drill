import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
destination = Path(sys.argv[1]).resolve()
if destination.exists():
    raise SystemExit('Choose a new demo directory; existing directories are preserved.')
destination.mkdir(parents=True)
shutil.copy2(Path(__file__).with_name('parameters.json'), destination / 'parameters.json')
subprocess.run(['git', 'init', '-q', str(destination)], check=True)
subprocess.run(['git', '-C', str(destination), 'config', 'user.email', 'demo@example.invalid'], check=True)
subprocess.run(['git', '-C', str(destination), 'config', 'user.name', 'Drill Demo'], check=True)
subprocess.run(['git', '-C', str(destination), 'add', 'parameters.json'], check=True)
subprocess.run(['git', '-C', str(destination), 'commit', '-qm', 'Start integer target search'], check=True)

def hub(command, *arguments):
    output = subprocess.check_output([sys.executable, str(root / 'hub.py'), command, '--repo', str(destination), '--campaign', 'demo', *arguments], text=True)
    return json.loads(output)

hub('init', '--config', str(Path(__file__).with_name('hub.json')))
baseline = hub('baseline')
result = hub('run', '--worker', 'researcher', '--iterations', '5')
report = hub('dashboard')
print(json.dumps({'repository': str(destination), 'baseline': baseline['score'], 'final': result['attempts'][-1]['score'], 'experiments': len(result['attempts']), 'dashboard': report['path']}, indent=2))
