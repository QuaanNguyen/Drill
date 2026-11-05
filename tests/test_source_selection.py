import json
import unittest

import test_cli
import test_materialize
from drill.materialize import archive


class SourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.flow = test_cli.WorkflowTests()
        self.flow.setUp()
        self.addCleanup(self.flow.doCleanups)

    def add_unavailable_model(self):
        f = self.flow
        (f.repo / 'unrelated-model.bin').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:' + 'e' * 64 + '\nsize 123\n')
        f.git('add', 'unrelated-model.bin')
        f.git('commit', '-qm', 'Retain an unrelated large-file pointer')

    def test_only_declared_sources_are_snapshotted_and_assets_are_independent(self):
        f = self.flow
        self.add_unavailable_model()
        f.config['schema_version'] = 3
        f.config['evaluator']['source_paths'] = ['measurement.json']
        f.config['evaluator']['assets'] = ['measurement.json']
        self.assertEqual(f.initialize()['verdict'], 'BASELINE')
        self.assertEqual(f.step({'value': 12})['verdict'], 'ACCEPTED')
        source = f.campaign / 'attempts/000002/source'
        self.assertEqual([p.name for p in source.iterdir()], ['measurement.json'])
        self.assertEqual(json.loads((f.campaign / 'evaluation/assets/measurement.json').read_text())['value'], 10)
        request = json.loads((f.campaign / 'attempts/000002/request.json').read_text())
        self.assertEqual(request['source']['paths'], ['measurement.json'])
        self.assertEqual(f.cli('status')['incumbent']['score'], 12)

    def test_selected_lfs_data_still_requires_materialization(self):
        f = self.flow
        self.add_unavailable_model()
        f.config['schema_version'] = 3
        f.config['evaluator']['source_paths'] = ['measurement.json', 'unrelated-model.bin']
        f.initialize(baseline=False)
        result = f.cli('baseline')
        self.assertEqual(result['verdict'], 'INVALID')
        self.assertIn('materialization.lfs', result['reason'])
        self.assertIsNone(result['score'])

    def test_asset_capture_does_not_materialize_unrelated_repository_files(self):
        f = self.flow
        self.add_unavailable_model()
        f.config['evaluator']['assets'] = ['measurement.json']
        f.initialize(baseline=False)
        self.assertTrue((f.campaign / 'evaluation/assets/measurement.json').is_file())
        self.assertFalse((f.campaign / 'evaluation/assets/unrelated-model.bin').exists())

    def test_scope_validation_still_checks_unselected_candidate_changes(self):
        f = self.flow
        f.config.update(schema_version=3, research={'brief': 'Improve only the measurement.', 'editable_paths': ['measurement.json']})
        f.config['evaluator']['source_paths'] = ['measurement.json']
        f.initialize()
        (f.repo / 'unselected.txt').write_text('An unselected file is not outside the scope check.')
        f.git('add', 'unselected.txt')
        f.commit({'value': 12})
        self.assertEqual(f.cli('step', '--hypothesis', 'Scope covers the whole candidate commit.')['verdict'], 'INVALID')

    def test_source_selection_requires_version_3_and_exact_nonempty_paths(self):
        f = self.flow
        for schema, paths in [(1, ['measurement.json']), (2, ['measurement.json']), (3, []), (3, ['../file']), (3, ['measurement.json', 'measurement.json'])]:
            f.config['schema_version'] = schema
            f.config['evaluator']['source_paths'] = paths
            config = f.base / 'config.json'
            config.write_text(json.dumps(f.config))
            f.cli('init', '--config', str(config), ok=False)

    def test_selecting_a_missing_file_is_invalid_without_measurement(self):
        f = self.flow
        f.config['schema_version'] = 3
        f.config['evaluator']['source_paths'] = ['missing.py']
        result = f.initialize()
        self.assertEqual(result['verdict'], 'INVALID')
        self.assertIsNone(result['score'])

    def test_submodule_selection_only_materializes_the_declared_file(self):
        fixture = test_materialize.MaterializationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        child = fixture.create_repo('child')
        (child / 'other.bin').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:' + 'd' * 64 + '\nsize 100\n')
        fixture.git(child, 'add', 'other.bin')
        fixture.git(child, 'commit', '-qm', 'Pin unrelated data in dependency')
        fixture.add_module(fixture.repo, child)
        fixture.cache_module(fixture.repo, child)
        target = fixture.root / 'selected'
        result = archive(fixture.repo, 'HEAD', target, {'submodules': True}, paths=['dependencies/child/source.txt'])
        self.assertEqual((target / 'dependencies/child/source.txt').read_text(), 'child')
        self.assertFalse((target / 'dependencies/child/other.bin').exists())
        self.assertEqual(len(result), 1)

    def test_unselected_submodules_are_not_acquired(self):
        fixture = test_materialize.MaterializationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        child = fixture.create_repo('child')
        fixture.add_module(fixture.repo, child)
        target = fixture.root / 'selected'
        self.assertEqual(archive(fixture.repo, 'HEAD', target, paths=['source.txt']), [])
        self.assertEqual((target / 'source.txt').read_text(), 'parent')
        self.assertFalse((target / 'dependencies').exists())
