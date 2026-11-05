import json
import unittest
from pathlib import Path

import test_cli


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.flow = test_cli.WorkflowTests()
        self.flow.setUp()
        self.addCleanup(self.flow.doCleanups)
        self.flow.config['schema_version'] = 2
        self.flow.config['research'] = {'brief': 'Improve the supplied measurement without changing its evaluator.', 'editable_paths': ['measurement.json'], 'max_iterations': 3, 'budget_seconds': 2}

    def test_scope_accepts_only_declared_regular_files(self):
        f = self.flow
        f.initialize()
        self.assertEqual(f.step({'value': 12})['verdict'], 'ACCEPTED')
        (f.repo / 'protected.txt').write_text('Changed outside the research scope.')
        f.git('add', 'protected.txt')
        f.git('commit', '-qm', 'Change protected input')
        result = f.cli('step', '--hypothesis', 'An invalid scope must never reach the evaluator.')
        self.assertEqual(result['verdict'], 'INVALID')
        self.assertIn('outside the research scope', result['reason'])
        self.assertFalse((f.campaign / 'attempts' / result['attempt_id'] / 'request-001.json').exists())
        self.assertEqual(f.cli('status')['incumbent']['score'], 12)

    def test_rename_and_symlink_cannot_escape_scope(self):
        f = self.flow
        f.initialize()
        f.git('mv', 'measurement.json', 'elsewhere.json')
        f.git('commit', '-qm', 'Rename outside scope')
        self.assertEqual(f.cli('step', '--hypothesis', 'A rename is a change to both paths.')['verdict'], 'INVALID')

    def test_symlink_candidate_is_rejected_before_evaluation(self):
        f = self.flow
        f.initialize()
        (f.repo / 'measurement.json').unlink()
        (f.repo / 'measurement.json').symlink_to('absent.json')
        f.git('add', 'measurement.json')
        f.git('commit', '-qm', 'Add a symlink')
        result = f.cli('step', '--hypothesis', 'A symlink is not an editable regular file.')
        self.assertEqual(result['verdict'], 'INVALID')
        self.assertIn('not a regular source file', result['reason'])

    def test_rejected_commit_is_preserved_and_next_parent_uses_incumbent(self):
        f = self.flow
        f.config['agent'] = {'adapter': 'agent.py', 'timeout_seconds': 10}
        (f.base / 'agent.py').write_text(test_cli.AGENT.replace('data["value"] += 2', 'data["value"] += -1 if len(request["history"]) == 1 else 2'))
        f.initialize()
        loop = f.cli('run', '--worker', 'researcher', '--iterations', '2')
        self.assertEqual([(row['verdict'], row['score']) for row in loop['attempts']], [('REJECTED', 9), ('ACCEPTED', 12)])
        worker = Path(loop['worker']['path'])
        parent = json.loads(f.git('show', 'HEAD^:measurement.json', cwd=worker))
        self.assertEqual(parent['value'], 10)
        rejected = loop['attempts'][0]['source_commit']
        self.assertEqual(json.loads(f.git('show', f'{rejected}:measurement.json'))['value'], 9)
        f.git('merge-base', '--is-ancestor', rejected, 'HEAD', cwd=worker)
        handoff = json.loads((sorted((f.campaign / 'agent-runs').iterdir())[-1] / 'request.json').read_text())
        self.assertEqual(handoff['research']['editable_paths'], ['measurement.json'])

    def test_current_agent_handoff_prepares_the_worker_and_respects_budget(self):
        f = self.flow
        f.initialize()
        worker = Path(f.cli('workspace', '--worker', 'researcher')['path'])
        f.commit({'value': 9}, cwd=worker)
        result = f.cli('step', '--worker', 'researcher', '--hypothesis', 'Measure a losing candidate.')
        self.assertEqual(result['verdict'], 'REJECTED')
        handoff = f.cli('run', '--worker', 'researcher', '--iterations', '2')
        self.assertEqual(handoff['mode'], 'current_agent')
        self.assertEqual(json.loads((worker / 'measurement.json').read_text())['value'], 10)
        self.assertEqual(handoff['research']['max_iterations'], 3)
        self.assertIn('budget', f.cli('run', '--iterations', '4', ok=False))
        (worker / 'measurement.json').write_text('Uncommitted work must survive.')
        self.assertIn('dirty', f.cli('run', '--iterations', '1', ok=False))
        self.assertEqual((worker / 'measurement.json').read_text(), 'Uncommitted work must survive.')

    def test_ignored_collision_is_preserved(self):
        f = self.flow
        f.initialize()
        worker = Path(f.cli('workspace', '--worker', 'researcher')['path'])
        f.git('rm', 'measurement.json', cwd=worker)
        f.git('commit', '-qm', 'Temporarily remove the editable source', cwd=worker)
        exclude = Path(f.git('rev-parse', '--path-format=absolute', '--git-path', 'info/exclude', cwd=worker))
        exclude.write_text(exclude.read_text() + '\n/measurement.json\n')
        (worker / 'measurement.json').write_text('An ignored local file must not be overwritten.')
        f.cli('run', '--iterations', '1', ok=False)
        self.assertEqual((worker / 'measurement.json').read_text(), 'An ignored local file must not be overwritten.')

    def test_pending_worker_stops_and_evaluator_budget_is_retained(self):
        f = self.flow
        f.initialize()
        worker = Path(f.cli('workspace', '--worker', 'researcher')['path'])
        f.commit({'value': 12, 'mode': 'pending'}, cwd=worker)
        result = f.cli('step', '--worker', 'researcher', '--hypothesis', 'Wait for the saved evaluation.')
        self.assertEqual(result['verdict'], 'PENDING')
        self.assertIn('incomplete', f.cli('run', '--iterations', '1', ok=False))
        request = json.loads((f.campaign / 'attempts' / result['attempt_id'] / 'request.json').read_text())
        self.assertEqual(request['research']['budget_seconds'], 2)

    def test_research_timeout_does_not_become_a_measurement(self):
        f = self.flow
        f.config['research']['budget_seconds'] = 0.3
        f.initialize()
        result = f.step({'value': 12, 'mode': 'timeout'})
        self.assertEqual(result['verdict'], 'INCONCLUSIVE')
        self.assertIsNone(result['score'])

    def test_invalid_scope_configuration_is_rejected(self):
        f = self.flow
        for paths in ([], ['.'], ['../source'], ['src//file'], ['.drill/settings.json'], ['measurement.json', 'measurement.json']):
            f.config['research']['editable_paths'] = paths
            path = f.base / 'hub.json'
            path.write_text(json.dumps(f.config))
            f.cli('init', '--config', str(path), ok=False)

    def test_git_pathspec_syntax_is_treated_as_an_exact_filename(self):
        f = self.flow
        name = ':(literal)measurement.json'
        f.config['research']['editable_paths'] = [name]
        f.initialize()
        (f.repo / name).symlink_to('measurement.json')
        f.git('--literal-pathspecs', 'add', name)
        f.git('commit', '-qm', 'Add a symlink with pathspec syntax in its name')
        result = f.cli('step', '--hypothesis', 'All names must be treated literally.')
        self.assertEqual(result['verdict'], 'INVALID')
        self.assertIn('not a regular source file', result['reason'])

    def test_interrupted_agent_request_stops_before_preparing_again(self):
        f = self.flow
        f.initialize()
        identity = f.cli('workspace', '--worker', 'researcher')
        run = f.campaign / 'agent-runs' / 'interrupted'
        run.mkdir()
        (run / 'request.json').write_text(json.dumps({'worker': identity}))
        self.assertIn('interrupted agent run', f.cli('run', '--iterations', '1', ok=False))

    def test_frozen_evaluator_asset_cannot_be_declared_editable(self):
        f = self.flow
        f.config['evaluator']['assets'] = ['measurement.json']
        path = f.base / 'hub.json'
        path.write_text(json.dumps(f.config))
        self.assertIn('frozen evaluator', f.cli('init', '--config', str(path), ok=False))

    def test_new_and_deleted_permitted_files_remain_valid_candidates(self):
        f = self.flow
        f.config['research']['editable_paths'].append('new-file.txt')
        f.initialize()
        (f.repo / 'new-file.txt').write_text('An allowed new file.')
        f.git('add', 'new-file.txt')
        f.commit({'value': 12})
        self.assertEqual(f.cli('step', '--hypothesis', 'Add permitted source.')['verdict'], 'ACCEPTED')
        f.git('rm', 'new-file.txt')
        f.commit({'value': 14})
        self.assertEqual(f.cli('step', '--hypothesis', 'Remove permitted source.')['verdict'], 'ACCEPTED')

    def test_framework_route_names_are_literal_and_do_not_expand_scope(self):
        f = self.flow
        name = 'src/[slug]/page.tsx'
        f.config['research']['editable_paths'].append(name)
        f.initialize()
        route = f.repo / name
        route.parent.mkdir(parents=True)
        route.write_text('Allowed literal route source.')
        f.git('--literal-pathspecs', 'add', name)
        f.commit({'value': 12})
        self.assertEqual(f.cli('step', '--hypothesis', 'Edit one exact framework route.')['verdict'], 'ACCEPTED')
        other = f.repo / 'src/other/page.tsx'
        other.parent.mkdir()
        other.write_text('Outside the declared exact path.')
        f.git('add', 'src/other/page.tsx')
        f.git('commit', '-qm', 'Try a neighboring route')
        self.assertEqual(f.cli('step', '--hypothesis', 'No wildcard expansion is permitted.')['verdict'], 'INVALID')

    def test_research_requires_versioned_configuration(self):
        f = self.flow
        f.config['schema_version'] = 1
        path = f.base / 'hub.json'
        path.write_text(json.dumps(f.config))
        self.assertIn('schema_version 2', f.cli('init', '--config', str(path), ok=False))
