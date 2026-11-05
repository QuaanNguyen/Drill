import json
import math
import re
from pathlib import Path


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', value):
        raise ValueError('Names must contain lowercase letters, digits, underscores, or hyphens, with at most 64 characters.')
    return value


def relative_path(value):
    path = Path(value)
    if not isinstance(value, str) or not value or path.is_absolute() or any(p in {'.', '..', '.git'} for p in path.parts):
        raise ValueError('Expected a relative path without traversal or Git metadata.')
    return path


def load_config(path):
    config = json.loads(path.read_text())
    if not isinstance(config, dict):
        raise ValueError('Configuration must be a JSON object.')
    if type(config.get('schema_version')) is not int or config['schema_version'] not in {1, 2} or not isinstance(config.get('name'), str) or not config['name'].strip():
        raise ValueError('Configuration requires schema_version 1 or 2 and a name.')
    if 'research' in config and config['schema_version'] != 2:
        raise ValueError('Research requires configuration schema_version 2 so older clients cannot silently ignore its restrictions.')
    objective = config['objective']
    if not isinstance(objective, dict):
        raise ValueError('Objective must be a JSON object.')
    if objective['direction'] not in {'maximize', 'minimize'}:
        raise ValueError('Objective direction must be maximize or minimize.')
    if not isinstance(objective['metric'], str) or not objective['metric'] or not isinstance(objective['unit'], str):
        raise ValueError('The objective requires a metric and unit.')
    margin = objective.setdefault('min_improvement', 0)
    if not number(margin) or margin < 0:
        raise ValueError('Minimum improvement must be a finite nonnegative number.')
    constraints = config.setdefault('constraints', [])
    if not isinstance(constraints, list):
        raise ValueError('Constraints must be a list.')
    for gate in constraints:
        if not isinstance(gate, dict):
            raise ValueError('Each constraint must be a JSON object.')
        if not isinstance(gate['metric'], str) or gate['op'] not in {'<=', '>=', '=='} or not number(gate['value']):
            raise ValueError('Each constraint requires a metric, comparison, and finite number.')
    for role in ('evaluator', 'agent'):
        if role not in config:
            if role == 'evaluator':
                raise ValueError('An evaluator adapter is required.')
            continue
        adapter = config[role]
        if not isinstance(adapter, dict):
            raise ValueError('Adapter configuration must be a JSON object.')
        source = (path.parent / adapter['adapter']).resolve()
        if not source.is_file():
            raise ValueError(f'{role} adapter does not exist: {source}')
        timeout = adapter.setdefault('timeout_seconds', 300)
        if not number(timeout) or timeout <= 0:
            raise ValueError('Adapter timeout must be positive.')
        command = adapter.setdefault('command', ['{python}', '{adapter}', '{request}', '{result}'])
        if not isinstance(command, list) or not command or any(not isinstance(token, str) or not token for token in command):
            raise ValueError('Adapter command must be a nonempty argument list.')
        replacements = dict.fromkeys(('python', 'adapter', 'request', 'result'), 'value')
        for token in command:
            try:
                token.format_map(replacements)
            except (KeyError, ValueError) as exc:
                raise ValueError('Unknown adapter command placeholder.') from exc
        if '{request}' not in ' '.join(command) or '{result}' not in ' '.join(command):
            raise ValueError('Adapter command must use the request and result placeholders.')
    workspace = config.setdefault('workspace', {'root': '.worktrees/drill'})
    if not isinstance(workspace, dict):
        raise ValueError('Workspace configuration must be a JSON object.')
    root = relative_path(workspace['root'])
    if len(root.parts) < 2 or root.parts[0] != '.worktrees':
        raise ValueError('Worktree root must be a directory inside .worktrees/.')
    assets = config['evaluator'].setdefault('assets', [])
    if not isinstance(assets, list) or len(assets) != len(set(assets)):
        raise ValueError('Evaluator assets must be a list of unique repository paths.')
    for asset in assets:
        relative_path(asset)
    materialization = config.setdefault('materialization', {})
    if not isinstance(materialization, dict) or set(materialization) - {'submodules', 'lfs', 'allow_network'}:
        raise ValueError('Materialization accepts submodules, lfs, and allow_network options.')
    for option in ('submodules', 'lfs', 'allow_network'):
        if type(materialization.setdefault(option, False)) is not bool:
            raise ValueError('Materialization options must be true or false.')
    if 'research' in config:
        from drill.research import validate_research
        config['research'] = validate_research(config['research'])
    return config


def validate_result(result, request, artifacts):
    if not isinstance(result, dict):
        raise ValueError('Evaluator response must be a JSON object.')
    if result.get('schema_version') != 1:
        raise ValueError('Evaluator response requires schema_version 1.')
    for field, expected in [('attempt_id', request['attempt_id']), ('source_commit', request['source']['commit']), ('evaluation_fingerprint', request['evaluation_fingerprint'])]:
        if result.get(field) != expected:
            raise ValueError(f'Evaluator response has a different {field}.')
    status = result.get('status')
    if status == 'pending':
        if not isinstance(result.get('job'), dict) or not result['job'].get('id'):
            raise ValueError('A pending response requires a durable job identifier.')
        return
    if status in {'failed', 'inconclusive'}:
        if not isinstance(result.get('reason'), str) or not result['reason'].strip():
            raise ValueError('Failed or inconclusive responses require a reason.')
        return
    if status != 'complete':
        raise ValueError('Unknown evaluator response status.')
    context = result.get('context')
    if not isinstance(context, dict) or not context:
        raise ValueError('A complete response requires a nonempty evaluation context.')
    json.dumps(context, allow_nan=False)
    metrics = result.get('metrics')
    if not isinstance(metrics, dict) or not metrics or any(not number(value) for value in metrics.values()):
        raise ValueError('Metrics must be finite numbers; booleans are not measurements.')
    required = {request['objective']['metric'], *(gate['metric'] for gate in request['constraints'])}
    if not required <= metrics.keys():
        raise ValueError('Response is missing an objective or constraint metric.')
    interval = result.get('interval')
    if interval is not None:
        score = metrics[request['objective']['metric']]
        if not isinstance(interval, list) or len(interval) != 2 or not all(number(x) for x in interval) or not interval[0] <= score <= interval[1]:
            raise ValueError('The uncertainty interval must contain the objective value.')
    evidence = result.get('artifacts')
    if not isinstance(evidence, list) or not evidence:
        raise ValueError('Complete responses require at least one evidence file.')
    for name in evidence:
        path = artifacts / relative_path(name)
        if not path.resolve().is_relative_to(artifacts.resolve()) or path.is_symlink() or not path.is_file():
            raise ValueError('Evidence must be a regular file inside the attempt artifacts directory.')


def constraints_pass(metrics, constraints):
    operations = {'<=': lambda a, b: a <= b, '>=': lambda a, b: a >= b, '==': lambda a, b: a == b}
    return all(operations[gate['op']](metrics[gate['metric']], gate['value']) for gate in constraints)


def assess(result, reference, objective, constraints, role):
    if not constraints_pass(result['metrics'], constraints):
        return 'REJECTED', 'One or more configured constraints failed.'
    if role == 'baseline':
        return 'BASELINE', 'Measured baseline passed the configured checks.'
    if result['context'] != reference['context']:
        return 'INCOMPARABLE', 'Evaluation context differs from the current reference.'
    metric = objective['metric']
    score, previous = result['metrics'][metric], reference['metrics'][metric]
    sign = 1 if objective['direction'] == 'maximize' else -1
    gain = sign * (score - previous)
    if gain <= 0 or gain < objective['min_improvement']:
        return 'REJECTED', 'The objective did not improve by the configured amount.'
    current_interval = result.get('interval') or [score, score]
    previous_interval = reference.get('interval') or [previous, previous]
    separation = current_interval[0] - previous_interval[1] if sign == 1 else previous_interval[0] - current_interval[1]
    if separation <= 0 or separation < objective['min_improvement']:
        return 'INCONCLUSIVE', 'Reported uncertainty does not establish the required improvement.'
    return 'ACCEPTED', 'The objective improved and all configured constraints passed.'
