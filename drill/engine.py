import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from drill.model import assess, identifier, load_config, validate_result
from drill.store import digest, fingerprint, incumbent, inventory, lock, now, package_inventory, read_json, records, save_record, validate_campaign, write_json
from drill.settings import load_goals, load_settings
from drill.research import prepare_worker, validate_candidate, validate_inputs
from drill.workspace import archive, contained, get_workspace, git, ignore_local, repository, revision, worker_revision


def campaign_path(repo, name):
    return contained(repo, f'.drill/campaigns/{identifier(name)}')


def launcher_source(runtime_hash):
    return f'''import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
root = Path(__file__).resolve().parent
metadata = root / "runtime.json"
if hashlib.sha256(metadata.read_bytes()).hexdigest() != {runtime_hash!r}:
    raise SystemExit("Frozen runtime metadata changed.")
manifest = json.loads(metadata.read_text())
for relative, expected in manifest["files"].items():
    path = root / relative
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit("Frozen campaign file changed: " + relative)
actual = {{".runtime/" + str(p.relative_to(root / ".runtime")) for p in (root / ".runtime").rglob("*.py")}}
expected = {{key for key in manifest["files"] if key.startswith(".runtime/")}}
if actual != expected:
    raise SystemExit("Frozen runtime source inventory changed.")
sys.path.insert(0, str(root / ".runtime"))
from drill.cli import main
main(bound=root)
'''


def initialize(repo, name, config_path):
    repo = repository(repo)
    campaign = campaign_path(repo, name)
    config = load_config(config_path.resolve())
    original_config = read_json(config_path.resolve())
    if 'materialization' not in original_config:
        config['materialization'] = load_settings(repo)['materialization']
    contained(repo, config['workspace']['root'])
    with lock(repo / '.drill' / '.workspace.lock'):
        if campaign.exists():
            raise ValueError('Campaign already exists. Resume it or choose a different campaign name.')
        initial = revision(repo, 'HEAD')
        validate_inputs(repo, initial, config, config_path.resolve())
        campaign.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.init-', dir=campaign.parent))
        try:
            (staging / '.runtime' / 'drill').mkdir(parents=True)
            for source in Path(__file__).parent.glob('*.py'):
                shutil.copy2(source, staging / '.runtime' / 'drill' / source.name)
            for role in ('evaluator', 'agent'):
                if role not in config:
                    continue
                source = (config_path.resolve().parent / config[role]['adapter']).resolve()
                destination = staging / 'evaluation' / role / ('adapter' + source.suffix)
                destination.parent.mkdir(parents=True)
                shutil.copy2(source, destination)
                config[role]['adapter'] = str(destination.relative_to(staging))
            if config['evaluator']['assets']:
                with tempfile.TemporaryDirectory(prefix='.inputs-', dir=staging) as temporary:
                    inputs = Path(temporary) / 'source'
                    materialized = archive(repo, initial, inputs, config.get('materialization'))
                    write_json(staging / 'evaluation' / 'materialization.json', materialized)
                    for relative in config['evaluator']['assets']:
                        source = inputs / relative
                        if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(inputs.resolve()):
                            raise ValueError(f'Evaluator asset must be a tracked regular file: {relative}')
                        target = staging / 'evaluation' / 'assets' / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, target)
            write_json(staging / 'config.json', config)
            (staging / 'AGENTS.md').write_text(instructions(repo, name, config))
            write_json(staging / 'agents.json', {'schema_version': 1, 'repo': str(repo), 'campaign': name, 'workspace_template': str(repo / config['workspace']['root'] / name / '{worker}'), 'branch_template': f'drill/{name}/{{worker}}', 'instructions': str(campaign / 'AGENTS.md'), 'create_workspace_command': [sys.executable, str(campaign / 'hub.py'), 'workspace', '--worker', '{worker}'], 'candidate_policy': 'Commit source changes in the named managed worktree before evaluation.'})
            files = {name: digest(staging / name) for name in ('config.json', 'AGENTS.md', 'agents.json')}
            files.update({'.runtime/' + key: value for key, value in package_inventory(staging / '.runtime').items()})
            files.update({'evaluation/' + key: value for key, value in inventory(staging / 'evaluation').items()})
            metadata = {'schema_version': 1, 'repo': str(repo), 'campaign': name, 'initial_revision': initial, 'files': files}
            write_json(staging / 'runtime.json', metadata)
            (staging / 'hub.py').write_text(launcher_source(digest(staging / 'runtime.json')))
            manifest = {**metadata, 'created_at': now(), 'evaluation_fingerprint': fingerprint({'config': config, 'files': files}), 'runtime_sha256': digest(staging / 'runtime.json'), 'frozen_files': {**files, 'hub.py': digest(staging / 'hub.py')}}
            write_json(staging / 'manifest.json', manifest)
            (staging / 'attempts').mkdir()
            (staging / 'workers').mkdir()
            (staging / 'agent-runs').mkdir()
            ignore_local(repo, ['.drill', config['workspace']['root']])
            staging.rename(campaign)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return {'campaign': str(campaign), 'launcher': str(campaign / 'hub.py'), 'baseline_revision': initial, 'workspace_root': str(repo / config['workspace']['root'])}


def instructions(repo, name, config):
    text = f'''# Research campaign {name}

Use the pinned launcher at {repo}/.drill/campaigns/{name}/hub.py.
Create your workspace with its workspace command and a stable worker name.
Your checkout belongs beneath {repo}/{config['workspace']['root']}/{name}/.
Never create worktrees beside the repository or choose random temporary checkout paths.
Do not reset, clean, remove, or reuse another worker's checkout or branch.
Commit your source changes before evaluating them with step and one concrete hypothesis.
Use the campaign status and decisions before proposing another experiment.
The evaluator, configuration, runtime, receipts, and other workers are read only.
Write research notes inside your own checkout and keep detailed measurement artifacts through the evaluator.
An ACCEPTED experiment passed this campaign's configured checks.
It does not authorize publication or replace a project's independent release and qualification requirements.
'''
    if 'research' in config:
        research = config['research']
        text += f'''
## Research brief

{research['brief']}

Only these exact files may change: {json.dumps(research['editable_paths'])}.
Each run allows at most {research['max_iterations']} experiments.
Each local evaluator invocation has a {research['budget_seconds']}-second ceiling.
Before the next experiment, call run again to prepare the accepted starting point.
The surrounding assistant retains its own tool permissions unless a restricted adapter is explicitly configured.
'''
    return text


class Campaign:
    def __init__(self, path):
        self.path = path.resolve()
        self.manifest = validate_campaign(self.path)
        if digest(self.path / 'runtime.json') != self.manifest['runtime_sha256']:
            raise ValueError('Frozen runtime metadata changed.')
        metadata = read_json(self.path / 'runtime.json')
        for key in ('repo', 'campaign', 'initial_revision'):
            if metadata[key] != self.manifest[key]:
                raise ValueError('Campaign identity changed after initialization.')
        self.config = read_json(self.path / 'config.json')
        self.repo = repository(Path(self.manifest['repo']))
        if campaign_path(self.repo, self.manifest['campaign']).resolve() != self.path:
            raise ValueError('Campaign does not match its repository-owned location.')

    def status(self):
        history = records(self.path)
        return {'campaign': self.manifest['campaign'], 'name': self.config['name'], 'objective': self.config['objective'], 'attempt_count': len(history), 'incumbent': incumbent(self.path), 'attempts': history, 'workspace_root': str(self.repo / self.config['workspace']['root'])}

    def workspace(self, worker):
        reference = incumbent(self.path)
        return get_workspace(self.path, self.manifest, self.config, worker, create=True, start=reference['source_commit'] if reference else None)

    def evaluate(self, role, ref=None, worker=None, hypothesis='Measure the committed starting baseline.'):
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            raise ValueError('An experiment requires a concrete hypothesis.')
        with lock(self.path / '.campaign.lock'):
            validate_campaign(self.path)
            reference = incumbent(self.path)
            if role == 'baseline' and any(row['role'] == 'baseline' and row['verdict'] == 'PENDING' for row in records(self.path)):
                raise ValueError('A baseline is pending. Resume its saved attempt before starting another.')
            if role == 'baseline' and reference:
                raise ValueError('Campaign already has a measured baseline. Create a new campaign to change it.')
            if role == 'candidate' and not reference:
                raise ValueError('Measure a passing baseline before evaluating candidates.')
            if worker:
                commit = worker_revision(self.path, self.manifest, self.config, worker)
            else:
                commit = revision(self.repo, ref or self.manifest['initial_revision'])
            existing = [int(p.name) for p in (self.path / 'attempts').iterdir() if p.name.isdigit()]
            attempt_id = f'{max(existing, default=0) + 1:06d}'
            directory = self.path / 'attempts' / attempt_id
            directory.mkdir()
            record = {'schema_version': 1, 'attempt_id': attempt_id, 'role': role, 'worker': worker, 'hypothesis': hypothesis.strip(), 'source_commit': commit, 'source_tree': git(self.repo, 'rev-parse', f'{commit}^{{tree}}'), 'parent': reference['attempt_id'] if reference else None, 'created_at': now(), 'verdict': 'RUNNING', 'score': None, 'metrics': {}, 'context': {}, 'interval': None, 'reason': 'Evaluation has not completed.'}
            save_record(directory, record)
            try:
                if 'research' in self.config:
                    validate_candidate(self.repo, self.manifest['initial_revision'], commit, self.config['research'])
                materialized = archive(self.repo, commit, directory / 'source', self.config.get('materialization'))
                write_json(directory / 'materialization.json', materialized)
                write_json(directory / 'source-hashes.json', inventory(directory / 'source'))
                (directory / 'artifacts').mkdir()
                request = {'schema_version': 1, 'attempt_id': attempt_id, 'role': role, 'operation': 'start', 'source': {'path': str(directory / 'source'), 'commit': commit, 'tree': record['source_tree']}, 'evaluation_fingerprint': self.manifest['evaluation_fingerprint'], 'objective': self.config['objective'], 'constraints': self.config['constraints'], 'assets': str(self.path / 'evaluation' / 'assets'), 'output_dir': str(directory / 'artifacts'), 'reference': reference}
                if 'research' in self.config:
                    request['research'] = self.config['research']
                write_json(directory / 'request.json', request)
                return self._execute(directory, record, request)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                record.update(verdict='INVALID', reason=str(exc))
                save_record(directory, record)
                return record

    def resume(self, attempt_id):
        if not isinstance(attempt_id, str) or len(attempt_id) != 6 or not attempt_id.isdigit():
            raise ValueError('Attempt must be a six-digit identifier.')
        with lock(self.path / '.campaign.lock'):
            directory = self.path / 'attempts' / attempt_id
            record = next((row for row in records(self.path) if row['attempt_id'] == attempt_id), None)
            if record is None:
                raise ValueError('Unknown attempt.')
            if record['verdict'] != 'PENDING':
                return record
            request = read_json(directory / 'request.json')
            responses = sorted(directory.glob('response-*.json'))
            request = dict(request, operation='poll', job=read_json(responses[-1])['job'])
            return self._execute(directory, record, request)

    def _execute(self, directory, record, request):
        try:
            validate_campaign(self.path)
            if inventory(directory / 'source') != read_json(directory / 'source-hashes.json'):
                raise ValueError('Committed source snapshot changed before evaluation.')
            index = len(list(directory.glob('request-*.json'))) + 1
            request_path = directory / f'request-{index:03d}.json'
            result_path = directory / f'response-{index:03d}.json'
            write_json(request_path, request)
            exit_code, timed_out = self._invoke('evaluator', request_path, result_path, directory / 'source', directory / f'process-{index:03d}')
            validate_campaign(self.path)
            if inventory(directory / 'source') != read_json(directory / 'source-hashes.json'):
                raise ValueError('Evaluator changed the committed source snapshot.')
            if timed_out:
                record.update(verdict='INCONCLUSIVE', reason='Evaluator timed out. Inspect the retained process logs before starting another attempt.')
            elif exit_code:
                record.update(verdict='FAILED', reason=f'Evaluator exited with code {exit_code}.')
            else:
                result = read_json(result_path)
                validate_result(result, request, directory / 'artifacts')
                status = result['status']
                if status == 'pending':
                    if request['operation'] == 'poll' and result['job']['id'] != request['job']['id']:
                        raise ValueError('Poll response changed the durable job identifier.')
                    record.update(verdict='PENDING', reason='External evaluation is pending.', job=result['job'])
                elif status in {'failed', 'inconclusive'}:
                    record.update(verdict=status.upper(), reason=result['reason'])
                else:
                    reference = incumbent(self.path)
                    if record['role'] == 'candidate' and reference is None:
                        raise ValueError('The reference evidence is no longer valid.')
                    verdict, reason = assess(result, reference, self.config['objective'], self.config['constraints'], record['role'])
                    record.update(verdict=verdict, reason=reason, metrics=result['metrics'], context=result['context'], interval=result.get('interval'), promotion_reference=reference['attempt_id'] if reference else None, artifacts={name: digest(directory / 'artifacts' / name) for name in result['artifacts']})
                    if verdict != 'INCOMPARABLE':
                        record['score'] = result['metrics'][self.config['objective']['metric']]
            record['updated_at'] = now()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            record.update(verdict='INVALID', score=None, metrics={}, reason=str(exc), updated_at=now())
        save_record(directory, record)
        return record

    def _invoke(self, role, request, result, cwd, log_prefix):
        spec = self.config[role]
        values = {'python': sys.executable, 'adapter': str(self.path / spec['adapter']), 'request': str(request), 'result': str(result)}
        command = [token.format_map(values) for token in spec['command']]
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        with log_prefix.with_suffix('.stdout.log').open('wb') as stdout, log_prefix.with_suffix('.stderr.log').open('wb') as stderr:
            process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr, env=environment, start_new_session=True)
            try:
                timeout = spec['timeout_seconds']
                if role == 'evaluator' and 'research' in self.config:
                    timeout = min(timeout, self.config['research']['budget_seconds'])
                process.wait(timeout=timeout)
                return process.returncode, False
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                return process.returncode, True
            except BaseException:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait()
                raise

    def run(self, worker, iterations):
        if type(iterations) is not int or not 1 <= iterations <= 100:
            raise ValueError('Iterations must be between 1 and 100.')
        if not incumbent(self.path):
            raise ValueError('Measure a passing baseline before starting the automatic research loop.')
        research = self.config.get('research')
        if research and iterations > research['max_iterations']:
            raise ValueError('Requested iterations exceed the saved research budget.')
        identity = self.workspace(worker)
        if 'agent' not in self.config:
            if research:
                with lock(self.path / 'workers' / f'{identifier(worker)}.lock'):
                    reference = incumbent(self.path)
                    prepare_worker(self, worker, reference)
                return {'mode': 'current_agent', 'worker': identity, 'iterations': iterations, 'research': research, 'incumbent': reference, 'objective': self.config['objective'], 'constraints': self.config['constraints'], 'history': records(self.path), 'instructions': str(self.path / 'AGENTS.md'), 'task': 'Read the research brief and edit only its exact permitted files in this owned checkout. Commit one candidate, evaluate it with the pinned launcher, and inspect the receipt. Call run again before the next experiment so the worker starts from the accepted result. Stop on an incomplete evaluation or at the iteration budget. The surrounding assistant retains its own tool permissions.'}
            return {'mode': 'current_agent', 'worker': identity, 'iterations': iterations, 'incumbent': incumbent(self.path), 'objective': self.config['objective'], 'constraints': self.config['constraints'], 'history': records(self.path), 'instructions': str(self.path / 'AGENTS.md'), 'goals': load_goals(self.repo), 'model_settings': load_settings(self.repo), 'task': 'Use the agent already working in this repository. Read the campaign instructions, make one hypothesis, edit and commit in this worker, then evaluate with drill step and inspect the result before continuing. Stop after the requested iteration budget. Do not select a provider or call a separate model API unless the user requests it.'}
        results = []
        with lock(self.path / 'workers' / f'{identifier(worker)}.lock'):
            for _ in range(iterations):
                reference = incumbent(self.path)
                if research:
                    prepare_worker(self, worker, reference)
                before = worker_revision(self.path, self.manifest, self.config, worker)
                run_dir = Path(tempfile.mkdtemp(prefix=f'{worker}-', dir=self.path / 'agent-runs'))
                request = {'schema_version': 1, 'worker': identity, 'incumbent': reference, 'objective': self.config['objective'], 'constraints': self.config['constraints'], 'history': records(self.path), 'instructions': str(self.path / 'AGENTS.md'), 'result_path': str(run_dir / 'response.json')}
                if research:
                    request['research'] = research
                    request['initial_revision'] = self.manifest['initial_revision']
                    request['starting_revision'] = before
                write_json(run_dir / 'request.json', request)
                code, timed_out = self._invoke('agent', run_dir / 'request.json', run_dir / 'response.json', Path(identity['path']), run_dir / 'agent')
                validate_campaign(self.path)
                if code or timed_out:
                    write_json(run_dir / 'outcome.json', {'status': 'FAILED', 'exit_code': code, 'timed_out': timed_out})
                    raise ValueError(f'Agent command failed. Its checkout and logs are preserved at {run_dir}.')
                response = read_json(run_dir / 'response.json')
                if not isinstance(response, dict) or not isinstance(response.get('hypothesis'), str) or not response['hypothesis'].strip():
                    raise ValueError(f'Agent response requires a concrete hypothesis. Logs are at {run_dir}.')
                after = worker_revision(self.path, self.manifest, self.config, worker)
                if after == before:
                    raise ValueError(f'Agent did not commit a new candidate. Logs are at {run_dir}.')
                result = self.evaluate('candidate', worker=worker, hypothesis=response['hypothesis'])
                write_json(run_dir / 'outcome.json', {'status': 'EVALUATED', 'attempt_id': result['attempt_id']})
                results.append(result)
                if result['verdict'] in {'PENDING', 'INVALID', 'FAILED', 'INCONCLUSIVE', 'INCOMPARABLE'}:
                    break
        return {'worker': identity, 'attempts': results}
