import argparse
import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tokenize
from datetime import datetime, timezone
from pathlib import Path


def run(root, arguments, environment, log_path):
    process = subprocess.run(arguments, cwd=root, env=environment, capture_output=True, text=True)
    log_path.write_text(process.stdout + process.stderr)
    if process.returncode:
        raise RuntimeError(f'Check failed; see {log_path}')
    return process.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--xor-repo', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    checks = {}
    core_log = output.parent / 'core-tests.log'
    run(root, [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'], environment, core_log)
    checks['core_tests'] = {'verdict': 'VERIFIED', 'log': core_log.name, 'result': core_log.read_text().strip()}
    with tempfile.TemporaryDirectory() as temporary:
        demo_log = output.parent / 'toy-demo.log'
        stdout = run(root, [sys.executable, 'examples/toy/demo.py', str(Path(temporary) / 'project')], environment, demo_log)
        demo = json.loads(stdout)
        if (demo['baseline'], demo['final'], demo['experiments']) != (25, 0, 5):
            raise RuntimeError('Toy demonstration did not reach its expected exact result.')
        report = Path(demo['dashboard'])
        document = report.read_text()
        for target in re.findall(r'href="([^"]+)"', document):
            if not (report.parent / target).is_file():
                raise RuntimeError(f'Dashboard evidence link is missing: {target}')
        if '#4AAEED' not in document or '<table>' not in document:
            raise RuntimeError('Dashboard did not contain its expected local content.')
        checks['toy_loop_and_report_content'] = {'verdict': 'VERIFIED', 'baseline': 25, 'final': 0, 'experiments': 5, 'evidence_links': 'all resolve'}
    if args.xor_repo:
        xor_log = output.parent / 'xor-adapter-tests.log'
        environment['XOR_REPO'] = str(args.xor_repo.resolve())
        run(root, [sys.executable, '-m', 'unittest', 'discover', '-s', 'examples/xor', '-p', 'test_*.py', '-q'], environment, xor_log)
        text = xor_log.read_text()
        if 'skipped=' in text or not re.search(r'Ran [1-9][0-9]* tests', text):
            raise RuntimeError('XOR adapter checks did not all execute.')
        checks['xor_adapter'] = {'verdict': 'VERIFIED', 'result': text.strip(), 'log': xor_log.name, 'model_measurement': False}
    else:
        checks['xor_adapter'] = {'verdict': 'NOT VERIFIED', 'reason': 'Provide --xor-repo and Node.js to run the optional adapter checks.'}
    for path in root.rglob('*.py'):
        if any(part in {'build', 'dist', '__pycache__', '.git', '.venv', '.checks', '.worktrees'} for part in path.relative_to(root).parts):
            continue
        source = path.read_text()
        tree = ast.parse(source)
        if any(token.type == tokenize.COMMENT for token in tokenize.generate_tokens(io.StringIO(source).readline)):
            raise RuntimeError(f'Unexpected source comment: {path}')
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(node):
                raise RuntimeError(f'Unexpected source docstring: {path}')
    checks['python_syntax_and_comment_policy'] = {'verdict': 'VERIFIED'}
    checks['dashboard_visual_inspection'] = {'verdict': 'NOT VERIFIED', 'reason': 'This verifier checks generated content and evidence links; visual inspection is separate.'}
    output.write_text(json.dumps({'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'checks': checks}, indent=2) + '\n')
    print(json.dumps({'verdict': 'VERIFIED', 'report': str(output), 'visual_inspection': 'NOT VERIFIED'}))


if __name__ == '__main__':
    main()
