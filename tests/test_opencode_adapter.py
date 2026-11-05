import json
import os
import signal
import time
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from drill.engine import Campaign

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = '''#!/usr/bin/env python3
import json
import os
import sys
import time
import signal
import subprocess
from pathlib import Path

mode = os.environ.get("DRILL_TEST_MODE", "success")
policy = json.loads(Path(os.environ["OPENCODE_CONFIG"]).read_text())["permission"]
if sys.argv[1] == "api":
    rules = [{"action": "*", "resource": "*", "effect": "deny"}]
    for action in ("read", "edit"):
        rules.extend({"action": action, "resource": resource, "effect": effect} for resource, effect in policy[action].items())
    if mode == "unsafe_policy":
        rules.append({"action": "bash", "resource": "*", "effect": "allow"})
    print(json.dumps({"location": {"directory": os.environ["PWD"] if mode != "wrong_directory" else str(Path.cwd().parent)}, "data": [{"id": "drill-research", "permissions": rules}]}))
    raise SystemExit()
if os.environ.get("DRILL_CAPTURE_PROMPT"):
    Path(os.environ["DRILL_CAPTURE_PROMPT"]).write_text(sys.argv[-1])
if mode in {"ignoring_parent", "orphan_child"}:
    child = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready', flush=True); time.sleep(60)"], stdout=subprocess.PIPE, text=True)
    child.stdout.readline()
    if mode == "ignoring_parent":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(os.environ["DRILL_PID_FILE"]).write_text(str(os.getpid()) + "\\n" + str(child.pid))
    time.sleep(60)
if mode == "descendant":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    def stopped(signum, frame):
        child.terminate()
        child.wait(timeout=2)
        raise SystemExit()
    signal.signal(signal.SIGTERM, stopped)
    Path(os.environ["DRILL_PID_FILE"]).write_text(str(os.getpid()) + "\\n" + str(child.pid))
    time.sleep(60)
if mode == "timeout":
    time.sleep(10)
if mode != "no_change":
    editable = json.loads(sys.argv[-1])["editable_files"][0]
    Path(editable).write_text("improved\\n")
if mode == "outside":
    Path("protected.txt").write_text("changed\\n")
if mode == "symlink":
    Path("candidate.txt").unlink()
    Path("candidate.txt").symlink_to("protected.txt")
if mode in {"denied", "unknown_tool"}:
    print(json.dumps({"type": "tool_use", "part": {"tool": "bash" if mode == "unknown_tool" else "edit", "state": {"status": "error" if mode == "denied" else "completed"}}}))
text = "invalid" if mode == "malformed" else json.dumps({"hypothesis": "A scoped edit improves the baseline."})
print(json.dumps({"type": "text", "part": {"text": text}}))
'''


class OpenCodeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.worker = self.base / 'worker'
        self.worker.mkdir()
        for arguments in [('init', '-q'), ('config', 'user.email', 'adapter@example.invalid'), ('config', 'user.name', 'Adapter Check')]:
            self.git(*arguments)
        (self.worker / 'candidate.txt').write_text('baseline\n')
        (self.worker / 'protected.txt').write_text('fixed\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Baseline')
        self.before = self.git('rev-parse', 'HEAD')
        self.request = self.base / 'request.json'
        self.result = self.base / 'result.json'
        self.configuration = {'worker': {'path': str(self.worker), 'branch': self.git('branch', '--show-current')}, 'research': {'brief': 'Improve the baseline.', 'editable_paths': ['candidate.txt'], 'budget_seconds': 10, 'max_iterations': 1}, 'objective': {'metric': 'quality', 'direction': 'maximize'}, 'constraints': [], 'incumbent': {'source_commit': self.before, 'score': 0}}
        self.launcher = self.base / 'assistant-fixture'
        self.launcher.write_text(LAUNCHER)
        self.launcher.chmod(0o755)

    def git(self, *arguments):
        return subprocess.check_output(['git', '-C', str(self.worker), *arguments], text=True).strip()

    def invoke(self, mode='success', *arguments):
        self.request.write_text(json.dumps(self.configuration))
        return subprocess.run([sys.executable, str(ROOT / 'examples/opencode/agent.py'), str(self.request), str(self.result), '--launcher', str(self.launcher), *arguments], cwd=self.worker, env=dict(os.environ, DRILL_TEST_MODE=mode), capture_output=True, text=True, timeout=8)

    def test_permitted_edit_is_committed_by_the_host(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(self.git('rev-parse', 'HEAD'), self.before)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual((self.worker / 'candidate.txt').read_text(), 'improved\n')
        self.assertEqual((self.worker / 'protected.txt').read_text(), 'fixed\n')
        self.assertIn('hypothesis', json.loads(self.result.read_text()))
        policy = json.loads((self.base / 'opencode-policy.json').read_text())
        self.assertTrue(any(rule == {'action': '*', 'resource': '*', 'effect': 'deny'} for rule in policy['permissions']))

    def test_failures_never_create_a_commit_or_response(self):
        for mode in ('unsafe_policy', 'wrong_directory', 'outside', 'denied', 'unknown_tool', 'malformed', 'no_change', 'symlink'):
            with self.subTest(mode=mode):
                result = self.invoke(mode)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertFalse(self.result.exists())
                self.assertEqual(self.git('rev-parse', 'HEAD'), self.before)
                self.git('restore', '--staged', '--worktree', '.')

    def test_dirty_checkout_and_path_patterns_are_refused(self):
        (self.worker / 'candidate.txt').write_text('existing edit\n')
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual((self.worker / 'candidate.txt').read_text(), 'existing edit\n')
        self.git('restore', '.')
        self.configuration['research']['editable_paths'] = ['*.txt']
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse((self.base / 'opencode-policy.json').exists())

    def test_literal_filenames_are_staged_without_pattern_expansion(self):
        for name in (' candidate.txt ', ':(literal)candidate.txt'):
            with self.subTest(name=name):
                self.git('--literal-pathspecs', 'mv', 'candidate.txt', name)
                (self.worker / name).write_text('baseline\n')
                self.git('--literal-pathspecs', 'add', '--', name)
                self.git('commit', '-qm', 'Use an exact filename')
                self.before = self.git('rev-parse', 'HEAD')
                self.configuration['research']['editable_paths'] = [name]
                result = self.invoke()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.worker / name).read_text(), 'improved\n')
                self.git('--literal-pathspecs', 'mv', name, 'candidate.txt')
                self.git('commit', '-qm', 'Restore fixture name')

    def test_outer_termination_stops_the_assistant_process_group(self):
        self.request.write_text(json.dumps(self.configuration))
        pid_file = self.base / 'assistant-pids'
        process = subprocess.Popen([sys.executable, str(ROOT / 'examples/opencode/agent.py'), str(self.request), str(self.result), '--launcher', str(self.launcher)], cwd=self.worker, env=dict(os.environ, DRILL_TEST_MODE='descendant', DRILL_PID_FILE=str(pid_file)), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            deadline = time.monotonic() + 4
            while not pid_file.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(pid_file.exists())
            pids = pid_file.read_text().splitlines()
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=5)
            states = subprocess.run(['ps', '-p', ','.join(pids), '-o', 'stat='], capture_output=True, text=True)
            self.assertIn(states.returncode, (0, 1), states.stderr)
            self.assertEqual(states.stderr, '')
            self.assertFalse(any(state.strip() and not state.strip().startswith('Z') for state in states.stdout.splitlines()), states.stdout)
            self.assertFalse(self.result.exists())
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()

    def test_custom_configuration_is_not_silently_replaced(self):
        for name in ('OPENCODE_CONFIG', 'OPENCODE_CONFIG_CONTENT', 'OPENCODE_CLI_CONFIG_CONTENT'):
            with self.subTest(name=name), mock.patch.dict(os.environ, {name: 'private-override-value'}):
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Custom configuration overrides are present', result.stderr)
                self.assertNotIn('private-override-value', result.stderr)
                self.assertEqual(self.git('rev-parse', 'HEAD'), self.before)

    def test_timeout_retains_logs_without_committing(self):
        result = self.invoke('timeout', '--timeout', '1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.before)
        self.assertTrue((self.base / 'opencode-events.jsonl').exists())
        self.assertFalse(self.result.exists())

    def test_campaign_timeout_stops_term_ignoring_assistant_groups(self):
        self.request.write_text(json.dumps(self.configuration))
        campaign = object.__new__(Campaign)
        campaign.path = self.base
        campaign.config = {'agent': {'adapter': str(ROOT / 'examples/opencode/agent.py'), 'command': ['{python}', '{adapter}', '{request}', '{result}', '--launcher', str(self.launcher)], 'timeout_seconds': 1}}
        for mode in ('ignoring_parent', 'orphan_child'):
            with self.subTest(mode=mode):
                pid_file = self.base / mode
                try:
                    with mock.patch.dict(os.environ, {'DRILL_TEST_MODE': mode, 'DRILL_PID_FILE': str(pid_file)}):
                        code, timed_out = campaign._invoke('agent', self.request, self.result, self.worker, self.base / ('outer-' + mode))
                    self.assertTrue(timed_out)
                    self.assertTrue(pid_file.exists())
                    pids = pid_file.read_text().splitlines()
                    states = subprocess.run(['ps', '-p', ','.join(pids), '-o', 'stat='], capture_output=True, text=True)
                    self.assertIn(states.returncode, (0, 1), states.stderr)
                    self.assertEqual(states.stderr, '')
                    self.assertFalse(any(state.strip() and not state.strip().startswith('Z') for state in states.stdout.splitlines()), states.stdout)
                    self.assertFalse(self.result.exists())
                finally:
                    if pid_file.exists():
                        try:
                            os.killpg(int(pid_file.read_text().splitlines()[0]), signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_recent_history_is_bounded_and_supplied_to_the_actual_launcher(self):
        self.configuration['history'] = [{'attempt_id': f'{index:06d}', 'hypothesis': 'h' * 4000, 'verdict': 'REJECTED', 'score': index, 'source_commit': 'c' * 40, 'reason': 'r' * 4000, 'private_artifact_body': 'not a prompt field'} for index in range(12)]
        captured = self.base / 'captured-prompt.json'
        with mock.patch.dict(os.environ, {'DRILL_CAPTURE_PROMPT': str(captured)}):
            result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = json.loads(captured.read_text())
        self.assertIn('history', prompt)
        self.assertEqual(prompt['history_total'], 12)
        self.assertEqual([row['attempt_id'] for row in prompt['history']], [f'{index:06d}' for index in range(2, 12)])
        for row in prompt['history']:
            self.assertEqual(len(row['hypothesis']), 256)
            self.assertEqual(len(row['reason']), 256)
            self.assertNotIn('private_artifact_body', row)
        self.assertLess(len(captured.read_bytes()), 65536)


if __name__ == '__main__':
    unittest.main()
