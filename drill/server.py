import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from drill.engine import Campaign, campaign_path
from drill.model import identifier
from drill.settings import add_goal, call_model, load_goals, load_settings, save_settings
from drill.workspace import ignore_local


def dashboard_state(repo):
    campaigns = []
    errors = []
    for path in sorted((repo / '.drill/campaigns').glob('*/manifest.json')):
        try:
            Campaign(path.parent)
            process = subprocess.run([sys.executable, '-B', str(path.parent / 'hub.py'), 'status'], capture_output=True, text=True, timeout=30)
            if process.returncode:
                raise ValueError('The saved campaign launcher could not read its evidence.')
            campaigns.append(json.loads(process.stdout))
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
            errors.append({'campaign': path.parent.name, 'error': str(exc)})
    return {'campaigns': campaigns, 'goals': load_goals(repo), 'settings': load_settings(repo), 'errors': errors}


def make_server(repo, port):
    ignore_local(repo, ['.drill'])
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, value, content_type='application/json'):
            data = value.encode() if isinstance(value, str) else json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type + '; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'SAMEORIGIN')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.valid_host():
                self.respond(403, {'error': 'Use the local dashboard address.'})
                return
            path = urlsplit(self.path).path
            try:
                if path in {'/', '/report.html', '/setup'}:
                    from drill.report import render
                    self.respond(200, render(dashboard_state(repo), live=True), 'text/html')
                elif path == '/api/state':
                    self.respond(200, dashboard_state(repo))
                elif path.startswith('/campaigns/'):
                    parts = path.strip('/').split('/')
                    if len(parts) != 5 or parts[2] != 'attempts' or parts[4] != 'record.json' or len(parts[3]) != 6 or not parts[3].isdigit():
                        raise ValueError('Unknown evidence path.')
                    campaign = campaign_path(repo, identifier(parts[1]))
                    Campaign(campaign)
                    evidence = campaign / 'attempts' / parts[3] / 'record.json'
                    if evidence.is_symlink() or not evidence.resolve().is_relative_to(campaign.resolve()):
                        raise ValueError('Evidence path leaves the campaign.')
                    self.respond(200, evidence.read_text())
                else:
                    self.respond(404, {'error': 'Not found.'})
            except (OSError, ValueError, KeyError) as exc:
                self.respond(400, {'error': str(exc)})

        def do_POST(self):
            origin = self.headers.get('Origin')
            if not self.valid_host() or origin not in {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}:
                self.respond(403, {'error': 'Requests must come from this local dashboard.'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 65536 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('Send a JSON request with at most 65536 bytes.')
                value = json.loads(self.rfile.read(length))
                path = urlsplit(self.path).path
                if path == '/api/goals':
                    result = add_goal(repo, value['text'], value.get('campaign'))
                elif path == '/api/settings':
                    result = save_settings(repo, value)
                elif path == '/api/model':
                    result = call_model(repo, value['prompt'])
                else:
                    self.respond(404, {'error': 'Not found.'})
                    return
                self.respond(200, result)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.respond(400, {'error': str(exc)})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def serve(repo, port=8765):
    server = make_server(repo, port)
    print(f'Drill dashboard: http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
