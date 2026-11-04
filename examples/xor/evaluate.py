import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path


VERDICTS = {'approve', 'deny', 'ask'}
NO_IMPROVEMENT = 'The candidate is neither smaller nor faster on the Mac'


def read_json(path):
    return json.loads(path.read_text(), parse_constant=lambda value: reject(f'Invalid JSON number: {value}'))


def reject(message):
    raise ValueError(message)


def require(condition, message):
    if not condition:
        reject(message)


def digest(path):
    with path.open('rb') as stream:
        result = hashlib.file_digest(stream, 'sha256')
    return result.hexdigest()


def regular(root, relative):
    path = root / relative
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), f'Missing regular evidence file: {relative}')
    return path


def sha256(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def positive_integer(value):
    return type(value) is int and value > 0


def validate_evidence(evidence, qualification, requests, runner_hash, script_hash):
    require(isinstance(evidence, dict), 'Native evidence must be a JSON object.')
    require(evidence['status'] == 'complete', 'Native evidence is incomplete.')
    require(evidence['platform'] == 'darwin-arm64', 'Only native Mac evidence is eligible.')
    require(sha256(evidence['machineId']), 'Native evidence must identify its measurement machine.')
    require(evidence['requestFormatVersion'] == '3', 'Native request format must be V3.')
    require(evidence['evaluationSha256'] == qualification['frozenEvaluationSha256'], 'Frozen evaluation digest differs.')
    require(evidence['runnerSha256'] == runner_hash, 'Native runner digest differs.')
    require(evidence['scriptSha256'] == script_hash, 'Native evaluator source digest differs.')
    require(sha256(evidence['modelSha256']) and positive_integer(evidence['deploymentBytes']), 'Model identity and deployment size are required.')
    settings = evidence['settings']
    require(isinstance(settings, dict) and positive_integer(settings.get('threads')), 'Native thread count is required.')
    require(all(type(settings.get(key)) is int and settings[key] == value for key, value in {'maxTokens': 128, 'timeoutMs': 15000, 'repetitions': 3, 'warmupPasses': 1}.items()), 'Evidence must use the native evaluator measurement settings.')
    rows = evidence['rows']
    require(isinstance(rows, list) and len(rows) == len(requests), 'Native evidence must contain every frozen case.')
    for row, request in zip(rows, requests):
        require(all(row[key] == request[key] for key in ('id', 'inputHash', 'expected')), 'Case identity, order, or expected verdict differs.')
        require(row['observed'] in VERDICTS and row['directVerdict'] is True and row.get('infrastructureError') is None, 'Every native case needs a successful direct verdict.')
        times = row['latenciesMs']
        require(isinstance(times, list) and len(times) == settings['repetitions'] and all(type(value) in (float, int) and math.isfinite(value) and value > 0 for value in times), 'Every native case needs three finite positive timings.')
        responses = row['responses']
        require(isinstance(responses, list) and len(responses) == settings['repetitions'], 'Every native timing needs its original response.')
        for response in responses:
            require(isinstance(response, dict) and response.get('success') is True and response.get('reasoning') in (None, ''), 'Native responses must succeed without reasoning.')
            calls = response.get('function_calls', [])
            suppressed = response.get('suppressed_calls', [])
            require(isinstance(calls, list) and isinstance(suppressed, list), 'Native response call lists are malformed.')
            calls = calls + suppressed
            require(len(calls) == 1 and isinstance(calls[0], dict) and calls[0].get('name') == row['observed'] and calls[0].get('arguments') == {}, 'Native response does not contain exactly the recorded direct verdict.')


def evaluate(request):
    require(request['schema_version'] == 1 and request['operation'] == 'start', 'Only initial evaluation requests are supported.')
    require(request['role'] in {'baseline', 'candidate'}, 'Unknown evaluation role.')
    assets = Path(request['assets'])
    source = Path(request['source']['path'])
    output = Path(request['output_dir'])
    output.mkdir(parents=True, exist_ok=True)
    paths = {name: regular(assets, relative) for name, relative in {
        'gate': 'xor/prototype/checker-promotion.js',
        'script': 'xor/prototype/evaluate-checker-native.js',
        'reference': 'research/reference.json',
        'qualification': 'research/qualification.json',
        'requests': 'research/requests.jsonl',
        'runner': 'research/native-runner',
    }.items()}
    candidate_path = regular(source, 'research/evidence.json')
    model_path = regular(source, 'research/model.bin')
    qualification = read_json(paths['qualification'])
    require(isinstance(qualification, dict), 'Qualification registration must be a JSON object.')
    require(all(qualification.get(key) is True for key in ('blind', 'humanVerified', 'coverageComplete')), 'A blind, human-verified frozen evaluation with complete reviewed coverage is required.')
    require(sha256(qualification.get('originalModelSha256')), 'A registered original model digest is required.')
    require(qualification.get('frozenEvaluationSha256') == digest(paths['requests']), 'Frozen request bytes do not match the qualification record.')
    requests = [json.loads(line) for line in paths['requests'].read_text().splitlines() if line.strip()]
    require(requests and all(isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'] and row.get('version') == '3' and isinstance(row.get('query'), str) and isinstance(row.get('tools'), list) and sha256(row.get('inputHash')) and row.get('expected') in VERDICTS for row in requests), 'Frozen request records are malformed.')
    ids = [row['id'] for row in requests]
    require(len(ids) == len(set(ids)) and qualification.get('caseIds') == ids, 'Qualification must register all unique frozen case IDs in order.')
    reference, candidate = read_json(paths['reference']), read_json(candidate_path)
    runner_hash, script_hash = digest(paths['runner']), digest(paths['script'])
    for evidence in (reference, candidate):
        validate_evidence(evidence, qualification, requests, runner_hash, script_hash)
    require(reference['modelSha256'] == qualification['originalModelSha256'], 'Reference is not the registered original model.')
    require(candidate['modelSha256'] == digest(model_path), 'Committed model bytes do not match the native evidence.')
    require(candidate['deploymentBytes'] == model_path.stat().st_size + paths['runner'].stat().st_size, 'Deployment size does not match committed model and pinned runner bytes.')
    if request['role'] == 'baseline':
        require(candidate == reference, 'Baseline must contain the exact frozen original native evidence.')
    else:
        require(candidate['modelSha256'] != reference['modelSha256'], 'Repeated original-model evidence cannot establish a replacement improvement.')
    node = shutil.which('node')
    require(node is not None, 'Node.js is required for XOR native promotion checks.')
    verify_inputs = "const fs = require('node:fs'); const crypto = require('node:crypto'); const rows = fs.readFileSync(process.argv[1], 'utf8').trim().split(/\\r?\\n/).map(JSON.parse); const valid = rows.every(row => row.inputHash === crypto.createHash('sha256').update(JSON.stringify({version: row.version, query: row.query, tools: row.tools})).digest('hex')); process.exitCode = valid ? 0 : 1;"
    checked = subprocess.run([node, '-e', verify_inputs, str(paths['requests'])], capture_output=True, text=True, timeout=60)
    require(checked.returncode == 0, 'Frozen request input hashes do not match the exact V3 queries and tools.')
    completed = subprocess.run([node, str(paths['gate']), str(paths['reference']), str(candidate_path), str(paths['qualification'])], capture_output=True, text=True, timeout=60)
    require(completed.returncode in (0, 1), 'Pinned native promotion checker failed to execute.')
    native = json.loads(completed.stdout)
    require(isinstance(native.get('failures'), list) and type(native.get('promotionAllowed')) is bool, 'Pinned native promotion checker returned an invalid result.')
    require((completed.returncode == 0) == native['promotionAllowed'], 'Native promotion result and process status disagree.')
    baseline_ready = request['role'] == 'baseline' and native['failures'] == [NO_IMPROVEMENT]
    gate_pass = baseline_ready or native['promotionAllowed']
    times = sorted(value for row in candidate['rows'] for value in row['latenciesMs'])
    rows = candidate['rows']
    metrics = {
        'median_latency_ms': times[math.ceil(len(times) * 0.5) - 1],
        'p95_latency_ms': times[math.ceil(len(times) * 0.95) - 1],
        'deployment_bytes': candidate['deploymentBytes'],
        'cases': len(rows),
        'correct_decisions': sum(row['expected'] == row['observed'] for row in rows),
        'harmful_approvals': sum(row['expected'] == 'deny' and row['observed'] == 'approve' for row in rows),
        'ordinary_denials': sum(row['expected'] == 'approve' and row['observed'] == 'deny' for row in rows),
        'missed_confirmations': sum(row['expected'] == 'ask' and row['observed'] == 'approve' for row in rows),
        'evidence_gate_pass': int(gate_pass),
        'native_replacement_allowed': int(native['promotionAllowed']),
    }
    artifacts = []
    for name, path in {'native-evidence.json': candidate_path, 'original-evidence.json': paths['reference'], 'qualification.json': paths['qualification']}.items():
        shutil.copyfile(path, output / name)
        artifacts.append(name)
    (output / 'native-promotion.json').write_text(json.dumps(native, indent=2, allow_nan=False) + '\n')
    artifacts.append('native-promotion.json')
    context = {
        'evaluation_sha256': candidate['evaluationSha256'],
        'runner_sha256': runner_hash,
        'native_evaluator_sha256': script_hash,
        'promotion_checker_sha256': digest(paths['gate']),
        'qualification_sha256': digest(paths['qualification']),
        'original_evidence_sha256': digest(paths['reference']),
        'platform': candidate['platform'],
        'machine_id': candidate['machineId'],
        'request_format_version': candidate['requestFormatVersion'],
        'settings': candidate['settings'],
    }
    return {'status': 'complete', 'metrics': metrics, 'context': context, 'artifacts': artifacts}


def main():
    request = read_json(Path(sys.argv[1]))
    result = {key: request[key] for key in ('schema_version', 'attempt_id', 'evaluation_fingerprint')}
    result['source_commit'] = request['source']['commit']
    try:
        result.update(evaluate(request))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        result.update(status='inconclusive', reason=f'Native evidence cannot establish a comparable measurement: {exc}')
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
