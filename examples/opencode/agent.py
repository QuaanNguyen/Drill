import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path


AGENT = 'drill-research'


def invoke(command, worker, environment, timeout, stdout=subprocess.PIPE, stderr=subprocess.PIPE):
    process = subprocess.Popen(command, cwd=worker, env=environment, stdout=stdout, stderr=stderr, text=True, start_new_session=True)
    try:
        output, errors = process.communicate(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise
    return subprocess.CompletedProcess(command, process.returncode, output, errors)


def git(worker, *arguments):
    process = subprocess.run(['git', '-C', str(worker), *arguments], capture_output=True, text=True)
    if process.returncode:
        raise ValueError(process.stderr.strip() or 'Git command failed.')
    return process.stdout.rstrip('\n')


def path_names(value):
    return [name for name in value.split('\0') if name]


def validate_paths(worker, names):
    if not isinstance(names, list) or not names or len(names) != len(set(names)):
        raise ValueError('Research requires unique editable files.')
    for name in names:
        if not isinstance(name, str) or not name or any(char in name for char in '*?[]{}\n\r\t\\'):
            raise ValueError('Editable files must be exact repository paths without patterns.')
        path = Path(name)
        target = worker / path
        if path.is_absolute() or path.as_posix() != name or any(part in {'.', '..', '.git', '.drill', '.worktrees'} for part in path.parts):
            raise ValueError('Editable files must stay inside the research checkout.')
        if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(worker):
            raise ValueError('Editable files must be existing regular files in the research checkout.')


def policy_for(worker, readable, editable):
    policy = {'*': 'deny', 'read': {'*': 'deny'}, 'edit': {'*': 'deny'}, 'external_directory': 'deny'}
    for action, names in [('read', readable), ('edit', editable)]:
        for name in names:
            policy[action][name] = 'allow'
            policy[action][str(worker / name)] = 'allow'
    return policy


def configuration(policy):
    return {'permission': policy, 'agent': {AGENT: {'mode': 'primary', 'description': 'Restricted baseline research', 'prompt': 'Work only on the supplied research brief and exact editable files. Use relative file paths. Open exact listed files directly; directory reads are denied. Never execute commands, use the network, delegate, load skills, or commit. Return only an unfenced JSON object with one hypothesis string.'}}}


def launch_environment(worker, config, config_path):
    if any(os.environ.get(name) for name in ('OPENCODE_CONFIG', 'OPENCODE_CONFIG_CONTENT', 'OPENCODE_CLI_CONFIG_CONTENT')):
        raise ValueError('Custom configuration overrides are present. Configure the provider through a global profile or OPENCODE_CONFIG_DIR before using restricted research.')
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    environment = dict(os.environ, PWD=str(worker), OPENCODE_CONFIG_PROJECT_DISABLE='true', OPENCODE_CONFIG=str(config_path))
    environment.pop('OPENCODE_CONFIG_CONTENT', None)
    environment.pop('OPENCODE_CLI_CONFIG_CONTENT', None)
    return environment


def verify_policy(agents, policy):
    agent = next((item for item in agents.get('data', []) if item.get('id') == AGENT), None)
    if agent is None:
        raise ValueError('The launcher did not expose the restricted research agent.')
    rules = agent.get('permissions', [])
    defaults = [index for index, rule in enumerate(rules) if rule.get('action') == '*' and rule.get('resource') == '*']
    if not defaults or rules[defaults[-1]].get('effect') != 'deny':
        raise ValueError('The launcher did not apply default-deny research permissions.')
    required = {(action, resource, 'allow') for action in ('read', 'edit') for resource, effect in policy[action].items() if effect == 'allow'}
    observed = set()
    for rule in rules[defaults[-1]:]:
        triple = (rule.get('action'), rule.get('resource'), rule.get('effect'))
        if triple[2] != 'deny' and triple not in required:
            raise ValueError('The launcher exposed an unexpected research permission.')
        observed.add(triple)
    if not required <= observed:
        raise ValueError('The launcher did not expose the exact research file permissions.')
    return {'agent': AGENT, 'permissions': rules[defaults[-1]:]}


def response_from(events):
    text = []
    for event in events:
        part = event.get('part', {})
        if event.get('type') == 'error':
            raise ValueError('OpenCode reported an error; inspect its retained event log.')
        if event.get('type') == 'tool_use':
            state = part.get('state', {})
            if part.get('tool') not in {'read', 'edit', 'write', 'apply_patch', 'multiedit'} or state.get('status') != 'completed':
                raise ValueError('A research tool failed or was refused; inspect its retained event log.')
        if event.get('type') == 'text':
            text.append(part.get('text', ''))
    if not text:
        raise ValueError('OpenCode did not return a research hypothesis.')
    message = text[-1].strip()
    if message.startswith('```json\n') and message.endswith('\n```'):
        message = message[8:-4]
    response = json.loads(message)
    if not isinstance(response, dict) or set(response) != {'hypothesis'} or not isinstance(response['hypothesis'], str) or not 1 <= len(response['hypothesis'].strip()) <= 2000:
        raise ValueError('OpenCode must return one JSON object containing a nonempty hypothesis.')
    return response


def run(request_path, result_path, launcher, model, timeout):
    request = json.loads(request_path.read_text())
    worker = Path(request['worker']['path']).resolve()
    if Path.cwd().resolve() != worker or Path(git(worker, 'rev-parse', '--show-toplevel')).resolve() != worker:
        raise ValueError('Run the adapter inside its managed research checkout.')
    branch = request['worker']['branch']
    before = git(worker, 'rev-parse', 'HEAD')
    if git(worker, 'branch', '--show-current') != branch or git(worker, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('The research worker must have its owned branch and a clean checkout.')
    research = request['research']
    editable = research['editable_paths']
    validate_paths(worker, editable)
    tracked = path_names(git(worker, 'ls-files', '-z'))
    readable = [name for name in tracked if (worker / name).is_file() and not (worker / name).is_symlink() and (worker / name).resolve().is_relative_to(worker) and not any(char in name for char in '*?[]{}\n\r\t\\')]
    policy = policy_for(worker, readable, editable)
    config = configuration(policy)
    environment = launch_environment(worker, config, result_path.parent / 'opencode-config.json')
    inspect = invoke([launcher, 'api', '--standalone', 'GET', '/api/agent'], worker, environment, 30)
    if inspect.returncode:
        raise ValueError('Unable to inspect the launcher permissions; no research was started.')
    effective = json.loads(inspect.stdout)
    location = effective.get('location', {}).get('directory')
    if not isinstance(location, str) or Path(location).resolve() != worker:
        raise ValueError('The launcher selected a different research working directory.')
    proof = verify_policy(effective, policy)
    (result_path.parent / 'opencode-policy.json').write_text(json.dumps(proof, indent=2) + '\n')
    history = request.get('history', [])
    recent = []
    for attempt in history[-10:]:
        summary = {key: attempt[key] for key in ('attempt_id', 'hypothesis', 'verdict', 'score', 'source_commit', 'reason') if key in attempt}
        recent.append({key: value[:256] if isinstance(value, str) else value for key, value in summary.items()})
    prompt = json.dumps({'working_directory': str(worker), 'instruction': 'Make one concrete improvement. Open exact listed files directly with relative paths; do not read directories. Read only listed repository files. Edit only the editable files. Do not guess other filesystem locations. Return only {"hypothesis":"why this change should improve the objective"}. The host will commit and evaluate your edits.', 'brief': research['brief'], 'editable_files': editable, 'baseline_file_examples': readable[:64], 'additional_baseline_files': max(0, len(readable) - 64), 'objective': request['objective'], 'constraints': request['constraints'], 'incumbent': request['incumbent'], 'history': recent, 'history_total': len(history), 'evaluation_budget_seconds': research['budget_seconds']})
    if len(prompt.encode()) > 65536:
        raise ValueError('The research prompt exceeds the adapter launch limit of 64 KiB.')
    command = [launcher, 'run', '--standalone', '--format', 'json', '--agent', AGENT]
    if model:
        command.extend(['--model', model])
    command.append(prompt)
    with (result_path.parent / 'opencode-events.jsonl').open('w') as stdout, (result_path.parent / 'opencode-stderr.log').open('w') as stderr:
        process = invoke(command, worker, environment, timeout, stdout, stderr)
    if process.returncode:
        raise ValueError('OpenCode failed; the worker and its logs are preserved.')
    events = [json.loads(line) for line in (result_path.parent / 'opencode-events.jsonl').read_text().splitlines() if line.strip()]
    response = response_from(events)
    if git(worker, 'rev-parse', 'HEAD') != before or git(worker, 'branch', '--show-current') != branch:
        raise ValueError('The assistant changed the worker commit or branch; no candidate was recorded.')
    changed = set(path_names(git(worker, 'diff', '--name-only', '-z', '--no-renames', 'HEAD')))
    changed.update(path_names(git(worker, 'ls-files', '--others', '--exclude-standard', '-z')))
    if not changed or not changed <= set(editable):
        raise ValueError('The assistant made no changes or changed files outside the editable scope.')
    validate_paths(worker, sorted(changed))
    git(worker, '--literal-pathspecs', 'add', '--', *sorted(changed))
    git(worker, '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', 'commit', '-m', response['hypothesis'])
    if git(worker, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('The research checkout remained dirty after committing.')
    result_path.write_text(json.dumps(response) + '\n')


def interrupted(signum, frame):
    raise SystemExit('Restricted OpenCode research interrupted.')


def main():
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser()
    parser.add_argument('request', type=Path)
    parser.add_argument('result', type=Path)
    parser.add_argument('--launcher', default='opencode')
    parser.add_argument('--model')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('Timeout must be positive.')
    try:
        run(args.request.resolve(), args.result.resolve(), args.launcher, args.model, args.timeout)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f'Restricted OpenCode research stopped: {exc}')


if __name__ == '__main__':
    main()
