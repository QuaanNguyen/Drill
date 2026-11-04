import hashlib
import json
import sys
from pathlib import Path

request = json.loads(Path(sys.argv[1]).read_text())
source = Path(request['source']['path'])
parameters = json.loads((source / 'parameters.json').read_text())
target = 7
error = (parameters['value'] - target) ** 2
output = Path(request['output_dir']) / 'measurement.json'
output.write_text(json.dumps({'input': parameters, 'target': target, 'squared_error': error}, indent=2) + '\n')
response = {
    'schema_version': 1,
    'attempt_id': request['attempt_id'],
    'source_commit': request['source']['commit'],
    'evaluation_fingerprint': request['evaluation_fingerprint'],
    'status': 'complete',
    'context': {'task': 'integer-target-v1', 'target_sha256': hashlib.sha256(str(target).encode()).hexdigest(), 'evaluation': 'exact-arithmetic'},
    'metrics': {'squared_error': error, 'constraint_violations': int(type(parameters['value']) is not int)},
    'artifacts': ['measurement.json'],
}
Path(sys.argv[2]).write_text(json.dumps(response) + '\n')
