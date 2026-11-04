import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class NativeAdapterTests(unittest.TestCase):
    def setUp(self):
        repository = os.environ.get('XOR_REPO')
        if not repository or not shutil.which('node'):
            self.skipTest('Set XOR_REPO and install Node.js to run the actual XOR native checker.')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.assets = self.root / 'assets'
        self.source = self.root / 'source'
        (self.assets / 'research').mkdir(parents=True)
        (self.source / 'research').mkdir(parents=True)
        for relative in ('xor/prototype/checker-promotion.js', 'xor/prototype/evaluate-checker-native.js'):
            destination = self.assets / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(repository) / relative, destination)
        self.runner = self.assets / 'research/native-runner'
        self.runner.write_bytes(b'synthetic-runner-fixture')
        self.model = self.source / 'research/model.bin'
        self.model.write_bytes(b'synthetic-original-model')
        row = {'id': 'synthetic-case', 'version': '3', 'inputHash': 'a' * 64, 'expected': 'deny', 'query': 'Synthetic adapter test only', 'tools': []}
        row['inputHash'] = hashlib.sha256(json.dumps({key: row[key] for key in ('version', 'query', 'tools')}, separators=(',', ':')).encode()).hexdigest()
        requests = self.assets / 'research/requests.jsonl'
        requests.write_text(json.dumps(row) + '\n')
        self.qualification = {'blind': True, 'humanVerified': True, 'coverageComplete': True, 'originalModelSha256': self.digest(self.model), 'frozenEvaluationSha256': self.digest(requests), 'caseIds': [row['id']]}
        self.write(self.assets / 'research/qualification.json', self.qualification)
        self.reference = {
            'status': 'complete',
            'platform': 'darwin-arm64',
            'machineId': 'b' * 64,
            'requestFormatVersion': '3',
            'evaluationSha256': self.digest(requests),
            'runnerSha256': self.digest(self.runner),
            'modelSha256': self.digest(self.model),
            'scriptSha256': self.digest(self.assets / 'xor/prototype/evaluate-checker-native.js'),
            'deploymentBytes': self.model.stat().st_size + self.runner.stat().st_size,
            'settings': {'threads': 4, 'maxTokens': 128, 'timeoutMs': 15000, 'repetitions': 3, 'warmupPasses': 1},
            'rows': [{'id': row['id'], 'inputHash': row['inputHash'], 'expected': 'deny', 'observed': 'deny', 'directVerdict': True, 'infrastructureError': None, 'latenciesMs': [10, 11, 12], 'responses': [{'success': True, 'function_calls': [{'name': 'deny', 'arguments': {}}]} for _ in range(3)]}],
        }
        self.write(self.assets / 'research/reference.json', self.reference)
        self.write(self.source / 'research/evidence.json', self.reference)

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value) + '\n')

    def run_adapter(self, role):
        request = {'schema_version': 1, 'attempt_id': '000001', 'evaluation_fingerprint': 'frozen-test-only', 'operation': 'start', 'role': role, 'assets': str(self.assets), 'source': {'path': str(self.source), 'commit': 'c' * 40}, 'output_dir': str(self.root / 'artifacts')}
        request_path, result_path = self.root / 'request.json', self.root / 'result.json'
        self.write(request_path, request)
        subprocess.run([sys.executable, str(Path(__file__).with_name('evaluate.py')), str(request_path), str(result_path)], check=True, capture_output=True, text=True)
        result = json.loads(result_path.read_text())
        self.assertEqual(result['source_commit'], request['source']['commit'])
        self.assertEqual(result['attempt_id'], request['attempt_id'])
        self.assertEqual(result['evaluation_fingerprint'], request['evaluation_fingerprint'])
        return result

    def candidate(self):
        self.model.write_bytes(b'synthetic-candidate-model')
        candidate = copy.deepcopy(self.reference)
        candidate['modelSha256'] = self.digest(self.model)
        candidate['deploymentBytes'] = self.model.stat().st_size + self.runner.stat().st_size
        candidate['rows'][0]['latenciesMs'] = [7, 8, 9]
        return candidate

    def test_baseline_retains_native_no_improvement(self):
        result = self.run_adapter('baseline')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['metrics']['median_latency_ms'], 11)
        self.assertEqual(result['metrics']['evidence_gate_pass'], 1)
        self.assertEqual(result['metrics']['native_replacement_allowed'], 0)
        self.assertTrue(all((self.root / 'artifacts' / name).is_file() for name in result['artifacts']))

    def test_full_hub_campaign_with_xor_shaped_repository(self):
        repository = self.root / 'xor-shaped-repository'
        shutil.copytree(self.assets, repository)
        shutil.copytree(self.source, repository, dirs_exist_ok=True)
        for arguments in (('init', '-q'), ('config', 'user.email', 'test@example.invalid'), ('config', 'user.name', 'XOR Fixture'), ('add', '.'), ('commit', '-qm', 'Frozen synthetic native baseline')):
            subprocess.run(['git', '-C', str(repository), *arguments], check=True, capture_output=True)
        tool = Path(__file__).resolve().parents[2] / 'hub.py'
        def hub(command, *arguments):
            process = subprocess.run([sys.executable, str(tool), command, '--repo', str(repository), '--campaign', 'xor-fixture', *arguments], check=True, capture_output=True, text=True)
            return json.loads(process.stdout)
        hub('init', '--config', str(Path(__file__).with_name('config.json').resolve()))
        baseline = hub('baseline')
        self.assertEqual(baseline['verdict'], 'BASELINE')
        self.assertEqual(baseline['score'], 11)
        workspace = Path(hub('workspace', '--worker', 'native-candidate')['path'])
        candidate = self.candidate()
        shutil.copy2(self.model, workspace / 'research/model.bin')
        self.write(workspace / 'research/evidence.json', candidate)
        for arguments in (('add', 'research/model.bin', 'research/evidence.json'), ('commit', '-qm', 'Synthetic matched native candidate')):
            subprocess.run(['git', '-C', str(workspace), *arguments], check=True, capture_output=True)
        result = hub('step', '--worker', 'native-candidate', '--hypothesis', 'Verify the native evidence adapter through the public hub commands.')
        self.assertEqual(result['verdict'], 'ACCEPTED')
        self.assertEqual(result['score'], 8)
        self.assertEqual(result['metrics']['native_replacement_allowed'], 1)
        self.assertEqual(hub('status')['incumbent']['attempt_id'], result['attempt_id'])

    def test_new_model_uses_native_promotion_checker(self):
        self.write(self.source / 'research/evidence.json', self.candidate())
        result = self.run_adapter('candidate')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['metrics']['median_latency_ms'], 8)
        self.assertEqual(result['metrics']['native_replacement_allowed'], 1)

    def test_incomplete_historical_summary_cannot_supply_score(self):
        self.write(self.source / 'research/evidence.json', {'status': 'go', 'cases': 1342, 'accuracy': 0.99})
        result = self.run_adapter('baseline')
        self.assertEqual(result['status'], 'inconclusive')
        self.assertNotIn('metrics', result)

    def test_harmful_approval_fails_native_gate(self):
        candidate = self.candidate()
        candidate['rows'][0]['observed'] = 'approve'
        for response in candidate['rows'][0]['responses']:
            response['function_calls'][0]['name'] = 'approve'
        self.write(self.source / 'research/evidence.json', candidate)
        result = self.run_adapter('candidate')
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['metrics']['evidence_gate_pass'], 0)
        self.assertEqual(result['metrics']['harmful_approvals'], 1)

    def test_original_remeasurement_cannot_claim_replacement(self):
        result = self.run_adapter('candidate')
        self.assertEqual(result['status'], 'inconclusive')
        self.assertNotIn('metrics', result)

    def test_corrupt_frozen_input_hash_rejects(self):
        requests_path = self.assets / 'research/requests.jsonl'
        request = json.loads(requests_path.read_text())
        request['query'] = 'Changed synthetic input with stale identity'
        self.write(requests_path, request)
        self.qualification['frozenEvaluationSha256'] = self.digest(requests_path)
        self.write(self.assets / 'research/qualification.json', self.qualification)
        self.reference['evaluationSha256'] = self.digest(requests_path)
        self.write(self.assets / 'research/reference.json', self.reference)
        self.write(self.source / 'research/evidence.json', self.reference)
        result = self.run_adapter('baseline')
        self.assertEqual(result['status'], 'inconclusive')
        self.assertNotIn('metrics', result)

    def test_unmatched_model_and_missing_timings_reject(self):
        for mutation in ('model', 'timings'):
            with self.subTest(mutation=mutation):
                candidate = self.candidate()
                if mutation == 'model':
                    candidate['modelSha256'] = 'd' * 64
                else:
                    candidate['rows'][0]['latenciesMs'] = [7, 8]
                self.write(self.source / 'research/evidence.json', candidate)
                result = self.run_adapter('candidate')
                self.assertEqual(result['status'], 'inconclusive')
                self.assertNotIn('metrics', result)


if __name__ == '__main__':
    unittest.main()
