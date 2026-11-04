import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ADAPTER = '''import hashlib
import json
import sys
from pathlib import Path

request = json.loads(Path(sys.argv[1]).read_text())
source = Path(request["source"]["path"])
data = json.loads((source / "measurement.json").read_text())
mode = data.get("mode", "complete")
if mode == "crash":
    raise SystemExit(3)
if mode == "timeout":
    import time
    time.sleep(10)
if mode == "mutate":
    (source / "measurement.json").write_text("changed")
if mode == "pending" and request["operation"] == "start":
    result = {"schema_version": 1, "status": "pending", "job": {"id": "job-1"}}
else:
    evidence = Path(request["output_dir"]) / "measurement.json"
    evidence.write_text(json.dumps(data))
    result = {"schema_version": 1, "status": "complete", "context": data.get("context", {"dataset": "v1", "machine": "cpu"}), "metrics": data.get("metrics", {"quality": data.get("value", 10), "errors": data.get("errors", 0)}), "artifacts": ["measurement.json"]}
    if "interval" in data:
        result["interval"] = data["interval"]
    if mode == "failed":
        result = {"schema_version": 1, "status": "failed", "reason": "unavailable"}
    if mode == "traversal":
        result["artifacts"] = ["../request.json"]
result["attempt_id"] = request["attempt_id"]
result["source_commit"] = request["source"]["commit"]
result["evaluation_fingerprint"] = request["evaluation_fingerprint"]
if mode == "wrong_identity":
    result["source_commit"] = "wrong"
Path(sys.argv[2]).write_text(json.dumps(result))
'''

AGENT = '''import json
import subprocess
import sys
from pathlib import Path

request = json.loads(Path(sys.argv[1]).read_text())
p = Path("measurement.json")
data = json.loads(p.read_text())
data["value"] += 2
p.write_text(json.dumps(data))
subprocess.run(["git", "add", "measurement.json"], check=True)
subprocess.run(["git", "commit", "-m", "Improve quality"], check=True, stdout=subprocess.DEVNULL)
Path(sys.argv[2]).write_text(json.dumps({"hypothesis": "A larger value improves the measured objective."}))
'''


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.repo = self.base / 'project'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.commit({'value': 10})
        (self.base / 'evaluator.py').write_text(ADAPTER)
        (self.base / 'agent.py').write_text(AGENT)
        self.config = {'schema_version': 1, 'name': 'Independent topic', 'objective': {'metric': 'quality', 'direction': 'maximize', 'unit': 'points', 'min_improvement': 1}, 'constraints': [{'metric': 'errors', 'op': '<=', 'value': 0}], 'evaluator': {'adapter': 'evaluator.py', 'timeout_seconds': 2}, 'workspace': {'root': '.worktrees/drill'}}

    def git(self, *args, cwd=None):
        result = subprocess.run(['git', '-C', str(cwd or self.repo), *args], text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def commit(self, data, cwd=None):
        target = cwd or self.repo
        (target / 'measurement.json').write_text(json.dumps(data))
        self.git('add', 'measurement.json', cwd=target)
        self.git('commit', '--allow-empty', '-qm', 'Measurement', cwd=target)
        return self.git('rev-parse', 'HEAD', cwd=target)

    def cli(self, command, *args, ok=True, pinned=False):
        launcher = self.campaign / 'hub.py' if pinned else ROOT / 'hub.py'
        common = [] if pinned else ['--repo', str(self.repo), '--campaign', 'trial']
        result = subprocess.run([sys.executable, str(launcher), command, *common, *args], text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.returncode == 0 else result.stderr

    @property
    def campaign(self):
        return self.repo / '.drill' / 'campaigns' / 'trial'

    def initialize(self, baseline=True):
        path = self.base / 'hub.json'
        path.write_text(json.dumps(self.config))
        self.cli('init', '--config', str(path))
        if baseline:
            return self.cli('baseline')

    def step(self, data):
        revision = self.commit(data)
        return self.cli('step', '--revision', revision, '--hypothesis', 'Test the configured objective.')

    def test_maximize_and_frozen_runtime(self):
        baseline = self.initialize()
        self.assertEqual(baseline['verdict'], 'BASELINE')
        self.assertEqual(self.step({'value': 12})['verdict'], 'ACCEPTED')
        self.assertEqual(self.step({'value': 11})['verdict'], 'REJECTED')
        status = self.cli('status', pinned=True)
        self.assertEqual(status['incumbent']['metrics']['quality'], 12)
        self.assertEqual(status['attempt_count'], 3)

    def test_minimize_negative_and_zero(self):
        self.config['objective']['direction'] = 'minimize'
        self.commit({'value': 0})
        self.initialize()
        self.assertEqual(self.step({'value': -2})['verdict'], 'ACCEPTED')
        self.assertEqual(self.step({'value': -2})['verdict'], 'REJECTED')

    def test_constraints_and_context(self):
        self.initialize()
        self.assertEqual(self.step({'value': 15, 'errors': 1})['verdict'], 'REJECTED')
        record = self.step({'value': 20, 'context': {'dataset': 'different'}})
        self.assertEqual(record['verdict'], 'INCOMPARABLE')
        self.assertIsNone(record['score'])
        self.assertEqual(self.cli('status')['incumbent']['metrics']['quality'], 10)

    def test_uncertainty_is_not_a_win(self):
        self.commit({'value': 10, 'interval': [9, 11]})
        self.initialize()
        self.assertEqual(self.step({'value': 12, 'interval': [10, 14]})['verdict'], 'INCONCLUSIVE')
        self.assertEqual(self.step({'value': 15, 'interval': [14, 16]})['verdict'], 'ACCEPTED')

    def test_pending_resume_uses_same_receipt(self):
        self.initialize()
        pending = self.step({'value': 15, 'mode': 'pending'})
        self.assertEqual(pending['verdict'], 'PENDING')
        done = self.cli('resume', '--attempt', pending['attempt_id'])
        self.assertEqual(done['verdict'], 'ACCEPTED')
        again = self.cli('resume', '--attempt', pending['attempt_id'])
        self.assertEqual(again, done)

    def test_failed_baseline_cannot_be_used(self):
        self.commit({'mode': 'failed'})
        self.initialize(baseline=False)
        self.assertEqual(self.cli('baseline')['verdict'], 'FAILED')
        self.step_error = self.cli('step', '--revision', 'HEAD', '--hypothesis', 'No reference.', ok=False)
        self.assertIn('baseline', self.step_error.lower())

    def test_invalid_numbers_and_missing_metrics(self):
        self.initialize()
        for metrics in ({'errors': 0}, {'quality': True, 'errors': 0}, {'quality': float('nan'), 'errors': 0}, {'quality': 99}):
            with self.subTest(metrics=metrics):
                record = self.step({'metrics': metrics})
                self.assertEqual(record['verdict'], 'INVALID')
                self.assertIsNone(record['score'])

    def test_process_and_identity_failures(self):
        self.initialize()
        for mode, verdict in [('crash', 'FAILED'), ('failed', 'FAILED'), ('wrong_identity', 'INVALID'), ('traversal', 'INVALID'), ('mutate', 'INVALID'), ('timeout', 'INCONCLUSIVE')]:
            with self.subTest(mode=mode):
                record = self.step({'value': 20, 'mode': mode})
                self.assertEqual(record['verdict'], verdict)
                self.assertIsNone(record['score'])

    def test_deterministic_owned_worktrees(self):
        self.initialize()
        first = self.cli('workspace', '--worker', 'alice')
        second = self.cli('workspace', '--worker', 'bob')
        expected = self.repo / '.worktrees' / 'drill' / 'trial'
        self.assertEqual(Path(first['path']), expected / 'alice')
        self.assertEqual(Path(second['path']), expected / 'bob')
        (expected / 'alice' / 'notes.txt').write_text('Keep my work.')
        self.assertEqual(self.cli('workspace', '--worker', 'alice'), first)
        self.assertEqual((expected / 'alice' / 'notes.txt').read_text(), 'Keep my work.')
        self.cli('step', '--worker', 'alice', '--hypothesis', 'Dirty checkout.', ok=False)
        self.cli('workspace', '--worker', '../outside', ok=False)
        foreign = expected / 'foreign'
        foreign.mkdir()
        (foreign / 'keep').write_text('foreign')
        self.cli('workspace', '--worker', 'foreign', ok=False)
        self.assertEqual((foreign / 'keep').read_text(), 'foreign')
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_config_and_runtime_tampering(self):
        self.initialize()
        config = self.campaign / 'config.json'
        config.write_text(config.read_text().replace('maximize', 'minimize'))
        self.cli('status', ok=False)
        self.cli('status', ok=False, pinned=True)

    def test_frozen_adapter_survives_original_edit(self):
        self.initialize()
        (self.base / 'evaluator.py').write_text('raise SystemExit(99)')
        self.assertEqual(self.step({'value': 12})['verdict'], 'ACCEPTED')

    def test_report_escapes_text_and_is_portable(self):
        self.initialize()
        self.cli('step', '--revision', 'HEAD', '--hypothesis', '<script>alert(1)</script>')
        output = self.cli('dashboard')
        html = Path(output['path']).read_text()
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert', html)
        self.assertIn('prefers-color-scheme', html)
        self.assertNotIn('#4AAEED', html)
        self.assertNotIn('cdn.', html)

    def test_current_agent_is_the_default_driver(self):
        self.initialize()
        result = self.cli('run', '--worker', 'current', '--iterations', '3')
        self.assertEqual(result['mode'], 'current_agent')
        self.assertEqual(result['iterations'], 3)
        self.assertEqual(result['worker']['worker'], 'current')
        self.assertEqual(self.cli('status')['attempt_count'], 1)
        self.assertIn('Do not select a provider', result['task'])

    def test_bounded_agent_loop(self):
        self.config['agent'] = {'adapter': 'agent.py', 'timeout_seconds': 10}
        self.initialize()
        result = self.cli('run', '--worker', 'robot', '--iterations', '2')
        self.assertEqual(len(result['attempts']), 2)
        self.assertTrue(all(row['verdict'] == 'ACCEPTED' for row in result['attempts']))
        self.assertEqual(self.cli('status')['incumbent']['metrics']['quality'], 14)

    def test_workspace_root_cannot_escape(self):
        self.config['workspace']['root'] = '../siblings'
        path = self.base / 'hub.json'
        path.write_text(json.dumps(self.config))
        self.cli('init', '--config', str(path), ok=False)
        self.assertFalse((self.base / 'siblings').exists())

    def test_saved_evidence_and_descendants_are_rechecked(self):
        self.initialize()
        self.step({'value': 12})
        path = self.campaign / 'attempts' / '000001' / 'artifacts' / 'measurement.json'
        path.write_text('changed')
        status = self.cli('status')
        self.assertIsNone(status['incumbent'])
        self.assertTrue(all(row['verdict'] == 'INVALID' for row in status['attempts']))

    def test_pending_evidence_cannot_be_replaced_before_poll(self):
        self.initialize()
        pending = self.step({'value': 15, 'mode': 'pending'})
        path = self.campaign / 'attempts' / pending['attempt_id'] / 'response-001.json'
        data = json.loads(path.read_text())
        data['job']['id'] = 'different-job'
        path.write_text(json.dumps(data))
        self.assertEqual(self.cli('resume', '--attempt', pending['attempt_id'])['verdict'], 'INVALID')

    def test_old_pending_candidate_cannot_replace_stronger_incumbent(self):
        self.initialize()
        pending = self.step({'value': 15, 'mode': 'pending'})
        self.assertEqual(self.step({'value': 20})['verdict'], 'ACCEPTED')
        result = self.cli('resume', '--attempt', pending['attempt_id'])
        self.assertEqual(result['verdict'], 'REJECTED')
        self.assertEqual(result['promotion_reference'], '000003')
        self.assertEqual(self.cli('status')['incumbent']['score'], 20)

    def test_older_pending_win_uses_promotion_order(self):
        self.initialize()
        pending = self.step({'value': 25, 'mode': 'pending'})
        self.assertEqual(self.step({'value': 20})['verdict'], 'ACCEPTED')
        result = self.cli('resume', '--attempt', pending['attempt_id'])
        self.assertEqual(result['verdict'], 'ACCEPTED')
        status = self.cli('status')
        self.assertEqual(status['incumbent']['score'], 25)
        self.assertEqual(status['incumbent']['attempt_id'], pending['attempt_id'])

    def test_pending_baseline_cannot_be_started_twice(self):
        self.commit({'mode': 'pending'})
        self.initialize(baseline=False)
        pending = self.cli('baseline')
        self.assertEqual(pending['verdict'], 'PENDING')
        self.cli('baseline', ok=False)
        self.assertEqual(self.cli('resume', '--attempt', pending['attempt_id'])['verdict'], 'BASELINE')

    def test_workspace_symlink_escape_is_rejected(self):
        self.initialize()
        outside = self.base / 'outside'
        outside.mkdir()
        parent = self.repo / '.worktrees'
        parent.mkdir(exist_ok=True)
        (parent / 'drill').symlink_to(outside, target_is_directory=True)
        self.cli('workspace', '--worker', 'alice', ok=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_contained_source_symlinks_are_supported(self):
        (self.repo / 'alias.json').symlink_to('measurement.json')
        self.git('add', 'alias.json')
        self.git('commit', '-qm', 'Add contained link')
        self.assertEqual(self.initialize()['verdict'], 'BASELINE')
        self.assertEqual(self.step({'value': 12})['verdict'], 'ACCEPTED')

    def test_evaluator_assets_are_pinned_to_initial_commit(self):
        (self.repo / 'dataset.json').write_text('{"version":1}')
        self.git('add', 'dataset.json')
        self.git('commit', '-qm', 'Freeze dataset')
        self.config['evaluator']['assets'] = ['dataset.json']
        self.initialize()
        (self.repo / 'dataset.json').write_text('{"version":2}')
        self.git('add', 'dataset.json')
        self.git('commit', '-qm', 'Change working dataset')
        asset = self.campaign / 'evaluation' / 'assets' / 'dataset.json'
        self.assertEqual(json.loads(asset.read_text()), {'version': 1})
        self.assertEqual(self.step({'value': 12})['verdict'], 'ACCEPTED')
        asset.write_text('changed')
        self.cli('status', ok=False)

    def test_generated_agent_policy_matches_workspace(self):
        self.initialize()
        policy = json.loads((self.campaign / 'agents.json').read_text())
        worker = self.cli('workspace', '--worker', 'alice')
        self.assertEqual(policy['workspace_template'].format(worker='alice'), worker['path'])
        self.assertEqual(policy['branch_template'].format(worker='alice'), worker['branch'])
        self.assertEqual(worker['instructions'], str(self.campaign / 'AGENTS.md'))
        self.assertTrue(Path(worker['agent_policy']).is_file())

    def simple_cli(self, command, *args, cwd=None, ok=True):
        result = subprocess.run([sys.executable, str(ROOT / 'hub.py'), command, *args], cwd=cwd or self.repo, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.returncode == 0 else result.stderr

    def test_selected_campaign_removes_repeated_options(self):
        self.initialize()
        self.assertEqual(self.simple_cli('status')['campaign'], 'trial')
        self.assertEqual(self.simple_cli('workspace')['worker'], 'researcher')
        self.commit({'value': 12})
        self.assertEqual(self.simple_cli('step', '--hypothesis', 'Improve the committed objective.')['verdict'], 'ACCEPTED')

    def test_default_campaign_and_explicit_selection(self):
        path = self.base / 'hub.json'
        path.write_text(json.dumps(self.config))
        result = self.simple_cli('init', '--config', str(path))
        self.assertTrue(result['campaign'].endswith('/default'))
        self.assertEqual(self.simple_cli('baseline')['verdict'], 'BASELINE')
        self.initialize()
        self.simple_cli('use', 'default')
        self.assertEqual(self.simple_cli('status')['campaign'], 'default')
        self.assertEqual(self.cli('status')['campaign'], 'trial')
        self.assertEqual(self.simple_cli('use', 'missing', ok=False).startswith('Error:'), True)
        self.assertEqual(self.simple_cli('status')['campaign'], 'default')

    def test_switching_selection_preserves_frozen_campaign(self):
        self.initialize()
        manifest = json.loads((self.campaign / 'manifest.json').read_text())
        protected = {name: (self.campaign / name).read_bytes() for name in manifest['frozen_files']}
        protected['runtime.json'] = (self.campaign / 'runtime.json').read_bytes()
        self.simple_cli('use', 'trial')
        self.simple_cli('status')
        self.assertEqual(protected, {name: (self.campaign / name).read_bytes() for name in protected})

    def test_worker_directory_selects_its_owner_campaign(self):
        self.initialize()
        identity = self.cli('workspace', '--worker', 'alice')
        worker = Path(identity['path'])
        self.commit({'value': 12}, cwd=worker)
        path = self.base / 'hub.json'
        self.simple_cli('init', '--config', str(path), '--campaign', 'another')
        self.assertEqual(self.simple_cli('status', cwd=worker)['campaign'], 'trial')
        result = self.simple_cli('step', '--hypothesis', 'Use the owned worker commit.', cwd=worker)
        self.assertEqual(result['verdict'], 'ACCEPTED')
        self.assertEqual(result['worker'], 'alice')

    def test_nested_repository_does_not_inherit_parent_selection(self):
        self.initialize()
        nested = self.repo / 'nested'
        nested.mkdir()
        self.git('init', '-q', cwd=nested)
        self.git('config', 'user.email', 'test@example.invalid', cwd=nested)
        self.git('config', 'user.name', 'Nested', cwd=nested)
        self.commit({'value': 5}, cwd=nested)
        error = self.simple_cli('status', cwd=nested, ok=False)
        self.assertIn('No campaign selected', error)

    def test_unmanaged_worktree_uses_its_current_commit(self):
        self.initialize()
        target = self.repo / '.worktrees' / 'manual'
        self.git('worktree', 'add', '-b', 'manual', str(target))
        commit = self.commit({'value': 20}, cwd=target)
        result = self.simple_cli('step', '--hypothesis', 'Measure this committed checkout.', cwd=target)
        self.assertEqual(result['source_commit'], commit)
        self.assertEqual(result['score'], 20)
        self.assertEqual(result['verdict'], 'ACCEPTED')

    def test_concurrent_selection_uses_independent_temporary_files(self):
        self.initialize()
        script = """import os
import sys
import time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import drill.store
import drill.cli
original = os.fsync
marker = Path(sys.argv[3])
def synchronized(descriptor):
    original(descriptor)
    marker.touch()
    deadline = time.monotonic() + 10
    while len(list(marker.parent.glob('ready-*'))) < 2:
        if time.monotonic() > deadline:
            raise RuntimeError('Second writer did not arrive.')
        time.sleep(.001)
drill.store.os.fsync = synchronized
sys.argv = ['drill', 'use', 'trial', '--repo', sys.argv[2]]
drill.cli.main()
"""
        processes = [subprocess.Popen([sys.executable, '-B', '-c', script, str(ROOT), str(self.repo), str(self.base / f'ready-{index}')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for index in range(2)]
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual(json.loads((self.repo / '.drill/active.json').read_text()), {'campaign': 'trial'})
        self.assertEqual(list((self.repo / '.drill').glob('.active.json-*.tmp')), [])

    def test_missing_lfs_input_remains_a_readable_invalid_attempt(self):
        (self.repo / 'model.bin').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:' + 'a' * 64 + '\nsize 10\n')
        self.git('add', 'model.bin')
        self.git('commit', '-qm', 'Track an unavailable data object')
        self.initialize(baseline=False)
        self.assertEqual(self.cli('baseline')['verdict'], 'INVALID')
        status = self.cli('status')
        self.assertIsNone(status['incumbent'])
        self.assertEqual(status['attempts'][0]['verdict'], 'INVALID')

    def test_setup_materializes_and_freezes_real_evaluator_asset_bytes(self):
        import hashlib
        payload = b'local model bytes for the integration fixture'
        oid = hashlib.sha256(payload).hexdigest()
        (self.repo / 'model.bin').write_text(f'version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {len(payload)}\n')
        self.git('add', 'model.bin')
        self.git('commit', '-qm', 'Register local data')
        cache = self.repo / '.git/lfs/objects' / oid[:2] / oid[2:4] / oid
        cache.parent.mkdir(parents=True)
        cache.write_bytes(payload)
        settings = self.repo / '.drill/settings.json'
        settings.parent.mkdir()
        settings.write_text(json.dumps({'materialization': {'lfs': True}}))
        self.config['evaluator']['assets'] = ['model.bin']
        self.assertEqual(self.initialize()['verdict'], 'BASELINE')
        self.assertEqual((self.campaign / 'evaluation/assets/model.bin').read_bytes(), payload)
        evidence = json.loads((self.campaign / 'attempts/000001/materialization.json').read_text())
        self.assertEqual(evidence[0]['sha256'], oid)
        self.assertTrue(json.loads((self.campaign / 'config.json').read_text())['materialization']['lfs'])

    def test_submodule_assets_and_source_use_the_exact_registered_commit(self):
        child = self.base / 'dependency'
        child.mkdir()
        self.git('init', '-q', cwd=child)
        self.git('config', 'user.email', 'fixture@example.invalid', cwd=child)
        self.git('config', 'user.name', 'Dependency Fixture', cwd=child)
        (child / 'data.json').write_text('{"dataset":"original"}')
        self.git('add', 'data.json', cwd=child)
        self.git('commit', '-qm', 'Register the dataset', cwd=child)
        expected = self.git('rev-parse', 'HEAD', cwd=child)
        self.git('-c', 'protocol.file.allow=always', 'submodule', 'add', str(child), 'dependency')
        self.git('commit', '-qm', 'Pin the dependency')
        self.config['materialization'] = {'submodules': True}
        self.config['evaluator']['assets'] = ['dependency/data.json']
        self.assertEqual(self.initialize()['verdict'], 'BASELINE')
        self.assertEqual((self.campaign / 'evaluation/assets/dependency/data.json').read_text(), '{"dataset":"original"}')
        (self.repo / 'dependency/data.json').write_text('{"dataset":"uncommitted"}')
        self.assertEqual(self.step({'value': 12})['verdict'], 'ACCEPTED')
        source = self.campaign / 'attempts/000002/source/dependency/data.json'
        self.assertEqual(source.read_text(), '{"dataset":"original"}')
        evidence = json.loads((self.campaign / 'attempts/000002/materialization.json').read_text())
        self.assertEqual(evidence[0]['commit'], expected)

    def test_reinitialization_preserves_evidence(self):
        self.initialize()
        before = (self.campaign / 'manifest.json').read_bytes()
        self.cli('init', '--config', str(self.base / 'hub.json'), ok=False)
        self.assertEqual(before, (self.campaign / 'manifest.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
