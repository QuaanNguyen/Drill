import json
import subprocess
import sys
from pathlib import Path

request = json.loads(Path(sys.argv[1]).read_text())
path = Path('parameters.json')
parameters = json.loads(path.read_text())
parameters['value'] += 1
path.write_text(json.dumps(parameters) + '\n')
subprocess.run(['git', 'add', 'parameters.json'], check=True)
subprocess.run(['git', 'commit', '-m', 'Move the parameter one step toward the target'], check=True)
Path(sys.argv[2]).write_text(json.dumps({'hypothesis': 'Increasing the parameter by one reduces squared error while it is below seven.'}) + '\n')
