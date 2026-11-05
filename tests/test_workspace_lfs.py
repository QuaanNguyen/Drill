import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('git-lfs'), 'Git LFS is required for the worker checkout regression.')
class WorkspaceLfsTests(unittest.TestCase):
    def test_workspace_does_not_fetch_missing_lfs_objects(self):
        requests = []
        class Endpoint(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(self.path)
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                body = b'{"message":"Downloads are unavailable in this fixture."}'
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST
            do_HEAD = do_POST

            def log_message(self, format, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Endpoint)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        environment.pop('GIT_LFS_SKIP_SMUDGE', None)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / 'project'
            repo.mkdir()
            def git(*args):
                return subprocess.run(['git', '-C', str(repo), *args], env=environment, capture_output=True, text=True, check=True)
            git('init', '-q')
            git('config', 'user.name', 'Workspace LFS Test')
            git('config', 'user.email', 'lfs@example.invalid')
            git('lfs', 'install', '--local')
            git('config', 'lfs.url', f'http://127.0.0.1:{server.server_port}/lfs')
            data = b'This object is deliberately unavailable.'
            pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(data).hexdigest()}\nsize {len(data)}\n'
            (repo / '.gitattributes').write_text('model.bin filter=lfs diff=lfs merge=lfs -text\n')
            (repo / 'model.bin').write_text(pointer)
            git('add', '.gitattributes', 'model.bin')
            git('commit', '-qm', 'Track an unavailable LFS object')
            adapter = root / 'evaluate.py'
            adapter.write_text('raise SystemExit("This checkout test must not evaluate source.")\n')
            configuration = root / 'research.json'
            configuration.write_text(json.dumps({'schema_version': 1, 'name': 'Local worker checkout', 'objective': {'metric': 'quality', 'direction': 'maximize', 'unit': 'points'}, 'evaluator': {'adapter': str(adapter)}, 'materialization': {'lfs': True, 'allow_network': False}}))
            initialized = subprocess.run([sys.executable, str(ROOT / 'hub.py'), 'init', '--repo', str(repo), '--config', str(configuration)], env=environment, capture_output=True, text=True)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            result = subprocess.run([sys.executable, str(ROOT / 'hub.py'), 'workspace', '--repo', str(repo)], env=environment, capture_output=True, text=True)
            self.assertEqual(requests, [], result.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            worker = Path(json.loads(result.stdout)['path'])
            self.assertEqual((worker / 'model.bin').read_text(), pointer)
            self.assertEqual((repo / 'model.bin').read_text(), pointer)
