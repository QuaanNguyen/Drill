import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from drill.server import make_server


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.server = make_server(self.repo, 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def request(self, path, body=None, origin=None):
        headers = {}
        if body is not None:
            headers = {'Content-Type': 'application/json', 'Origin': origin or self.base}
        request = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urlopen(request) as response:
            return json.load(response)

    def test_goals_and_setup_persist_without_credentials(self):
        self.assertEqual(self.request('/api/state')['settings']['driver'], 'current_agent')
        goal = self.request('/api/goals', {'text': 'Improve accuracy without more unsafe approvals.'})
        state = self.request('/api/state')
        self.assertEqual(state['goals'][0], goal)
        settings = self.request('/api/settings', {'driver': 'current_agent', 'materialization': {'submodules': True, 'lfs': True, 'allow_network': False}})
        self.assertTrue(settings['materialization']['lfs'])
        self.assertEqual(json.loads((self.repo / '.drill/settings.json').read_text()), settings)
        with self.assertRaises(HTTPError) as error:
            self.request('/api/settings', {'api_key': 'never-save-this'})
        self.assertEqual(error.exception.code, 400)
        self.assertNotIn('never-save-this', (self.repo / '.drill/settings.json').read_text())

    def test_cross_origin_changes_are_rejected(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/goals', {'text': 'Do not save.'}, origin='https://example.invalid')
        self.assertEqual(error.exception.code, 403)
        self.assertEqual(self.request('/api/state')['goals'], [])

    def test_model_call_is_explicit_and_uses_environment_credentials(self):
        with self.assertRaises(HTTPError):
            self.request('/api/model', {'prompt': 'Hello'})
        received = []
        class Provider(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append({'authorization': self.headers.get('Authorization'), 'body': json.loads(self.rfile.read(int(self.headers['Content-Length'])))})
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'choices': [{'message': {'content': 'Reply fixture-key-value'}}]}).encode())
        provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
        threading.Thread(target=provider.serve_forever, daemon=True).start()
        self.addCleanup(provider.server_close)
        self.addCleanup(provider.shutdown)
        settings = {'driver': 'model_api', 'endpoint': f'http://127.0.0.1:{provider.server_port}/chat', 'model': 'fixture-model', 'api_key_env': 'DRILL_FIXTURE_API_KEY'}
        self.request('/api/settings', settings)
        self.assertEqual(received, [])
        with patch.dict(os.environ, {'DRILL_FIXTURE_API_KEY': 'fixture-key-value'}):
            response = self.request('/api/model', {'prompt': 'Hello'})
        self.assertEqual(response['text'], 'Reply [redacted]')
        self.assertEqual(received[0]['authorization'], 'Bearer fixture-key-value')
        self.assertEqual(received[0]['body']['model'], 'fixture-model')
        self.assertNotIn('fixture-key-value', (self.repo / '.drill/settings.json').read_text())

    def test_malformed_environment_key_cannot_appear_in_an_error(self):
        self.request('/api/settings', {'driver': 'model_api', 'endpoint': 'http://127.0.0.1:1/chat', 'model': 'fixture', 'api_key_env': 'DRILL_FIXTURE_API_KEY'})
        for secret in ('fixture-secret-value\n', 'fixture-secret-value ' + chr(0x5b57)):
            with self.subTest(secret_kind='malformed'), patch.dict(os.environ, {'DRILL_FIXTURE_API_KEY': secret}):
                with self.assertRaises(HTTPError) as caught:
                    self.request('/api/model', {'prompt': 'Check the boundary.'})
                body = caught.exception.read().decode()
                self.assertNotIn('fixture-secret-value', body)
                self.assertIn('unsupported characters', body)

    def test_remote_plaintext_and_embedded_credentials_are_rejected(self):
        for endpoint in ['http://example.com/chat', 'https://key@example.com/chat', 'https://example.com/chat?key=value']:
            with self.subTest(endpoint=endpoint), self.assertRaises(HTTPError):
                self.request('/api/settings', {'driver': 'model_api', 'endpoint': endpoint, 'model': 'model'})


if __name__ == '__main__':
    unittest.main()
