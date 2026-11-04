import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from drill.materialize import archive


class MaterializationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.create_repo('parent')

    def git(self, repo, *arguments):
        return subprocess.check_output(['git', '-C', str(repo), *arguments], text=True, stderr=subprocess.PIPE).strip()

    def create_repo(self, name):
        path = self.root / name
        path.mkdir()
        self.git(path, 'init', '-q')
        self.git(path, 'config', 'user.name', 'Materialization Test')
        self.git(path, 'config', 'user.email', 'test@example.invalid')
        (path / 'source.txt').write_text(name)
        self.git(path, 'add', '.')
        self.git(path, 'commit', '-qm', 'Initial source')
        return path

    def add_module(self, parent, child, relative='dependencies/child', name='child'):
        oid = self.git(child, 'rev-parse', 'HEAD')
        self.git(parent, 'config', '-f', '.gitmodules', f'submodule.{name}.path', relative)
        self.git(parent, 'config', '-f', '.gitmodules', f'submodule.{name}.url', str(child))
        self.git(parent, 'add', '.gitmodules')
        self.git(parent, 'update-index', '--add', '--cacheinfo', f'160000,{oid},{relative}')
        self.git(parent, 'commit', '-qm', 'Register exact submodule')
        return oid

    def cache_module(self, parent, child, name='child'):
        common = Path(self.git(parent, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
        target = common / 'modules' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        self.git(parent, 'clone', '--bare', str(child), str(target))
        return target

    def add_pointer(self, data=b'actual model bytes', size=None):
        oid = hashlib.sha256(data).hexdigest()
        (self.repo / 'model.bin').write_text(f'version https://git-lfs.github.com/spec/v1\noid sha256:{oid}\nsize {len(data) if size is None else size}\n')
        self.git(self.repo, 'add', 'model.bin')
        self.git(self.repo, 'commit', '-qm', 'Register LFS data')
        common = Path(self.git(self.repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
        target = common / 'lfs/objects' / oid[:2] / oid[2:4] / oid
        return oid, target

    def test_submodule_requires_explicit_opt_in(self):
        child = self.create_repo('child')
        self.add_module(self.repo, child)
        with self.assertRaisesRegex(ValueError, 'materialization.submodules'):
            archive(self.repo, 'HEAD', self.root / 'snapshot')

    def test_local_module_uses_exact_commit_without_changing_checkout(self):
        child = self.create_repo('child')
        expected = self.add_module(self.repo, child)
        self.cache_module(self.repo, child)
        (child / 'source.txt').write_text('newer source')
        self.git(child, 'commit', '-qam', 'Newer source')
        before = self.git(self.repo, 'status', '--porcelain')
        result = archive(self.repo, 'HEAD', self.root / 'snapshot', {'submodules': True})
        self.assertEqual((self.root / 'snapshot/dependencies/child/source.txt').read_text(), 'child')
        self.assertEqual(result, [{'kind': 'submodule', 'path': 'dependencies/child', 'commit': expected}])
        self.assertEqual(self.git(self.repo, 'status', '--porcelain'), before)

    def test_nested_registered_submodules_are_materialized(self):
        child = self.create_repo('child')
        grandchild = self.create_repo('grandchild')
        self.add_module(child, grandchild, 'nested/grandchild', 'grandchild')
        self.add_module(self.repo, child)
        registered = self.cache_module(self.repo, child)
        self.cache_module(registered, grandchild, 'grandchild')
        result = archive(self.repo, 'HEAD', self.root / 'snapshot', {'submodules': True})
        self.assertEqual((self.root / 'snapshot/dependencies/child/nested/grandchild/source.txt').read_text(), 'grandchild')
        self.assertEqual(len(result), 2)

    def test_missing_module_fails_without_fetching(self):
        child = self.create_repo('child')
        self.add_module(self.repo, child)
        with self.assertRaisesRegex(ValueError, 'Downloads are disabled'):
            archive(self.repo, 'HEAD', self.root / 'snapshot', {'submodules': True})
        self.assertFalse((self.repo / '.git/modules').exists())

    def test_explicit_download_fetches_into_owned_temporary_store(self):
        child = self.create_repo('child')
        self.add_module(self.repo, child)
        before = self.git(self.repo, 'status', '--porcelain')
        result = archive(self.repo, 'HEAD', self.root / 'snapshot', {'submodules': True, 'allow_network': True})
        self.assertEqual((self.root / 'snapshot/dependencies/child/source.txt').read_text(), 'child')
        self.assertEqual(len(result), 1)
        self.assertFalse((self.repo / '.git/modules').exists())
        self.assertEqual(self.git(self.repo, 'status', '--porcelain'), before)
        self.assertEqual(list(self.root.glob('.drill-materialize-*')), [])

    def test_explicit_download_resolves_relative_submodule_url(self):
        child = self.create_repo('child')
        self.add_module(self.repo, child)
        self.git(self.repo, 'config', '-f', '.gitmodules', 'submodule.child.url', '../child')
        self.git(self.repo, 'add', '.gitmodules')
        self.git(self.repo, 'commit', '-qm', 'Use relative submodule URL')
        result = archive(self.repo, 'HEAD', self.root / 'snapshot', {'submodules': True, 'allow_network': True})
        self.assertEqual((self.root / 'snapshot/dependencies/child/source.txt').read_text(), 'child')
        self.assertEqual(len(result), 1)

    def test_lfs_defaults_reject_pointer_text(self):
        self.add_pointer()
        with self.assertRaisesRegex(ValueError, 'materialization.lfs'):
            archive(self.repo, 'HEAD', self.root / 'snapshot')

    def test_lfs_copies_and_hashes_local_object(self):
        data = b'actual model bytes'
        oid, target = self.add_pointer(data)
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        result = archive(self.repo, 'HEAD', self.root / 'snapshot', {'lfs': True})
        self.assertEqual((self.root / 'snapshot/model.bin').read_bytes(), data)
        self.assertEqual(result, [{'kind': 'lfs', 'path': 'model.bin', 'sha256': oid, 'size': len(data)}])
        self.assertTrue((self.repo / 'model.bin').read_text().startswith('version https://git-lfs'))

    def test_missing_lfs_object_fails_without_fetching(self):
        self.add_pointer()
        with self.assertRaisesRegex(ValueError, 'Downloads are disabled'):
            archive(self.repo, 'HEAD', self.root / 'snapshot', {'lfs': True})

    def test_corrupt_lfs_object_and_wrong_size_are_rejected(self):
        oid, target = self.add_pointer(b'original')
        target.parent.mkdir(parents=True)
        target.write_bytes(b'corrupt!')
        with self.assertRaisesRegex(ValueError, 'hash'):
            archive(self.repo, 'HEAD', self.root / 'snapshot', {'lfs': True})
        target.write_bytes(b'short')
        with self.assertRaisesRegex(ValueError, 'size'):
            archive(self.repo, 'HEAD', self.root / 'other', {'lfs': True})

    def test_explicit_lfs_fetch_uses_owned_cache(self):
        if shutil.which('git-lfs') is None:
            self.skipTest('Git LFS is needed for the explicit download integration check.')
        data = b'actual model bytes'
        oid, target = self.add_pointer(data)
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        (self.repo / '.gitattributes').write_text('model.bin filter=lfs diff=lfs merge=lfs -text\n')
        self.git(self.repo, 'add', '.gitattributes')
        self.git(self.repo, 'commit', '-qm', 'Declare LFS file')
        clone = self.root / 'source-clone'
        self.git(self.repo, 'clone', '--no-checkout', str(self.repo), str(clone))
        before = self.git(clone, 'status', '--porcelain')
        cached_before = {str(path.relative_to(clone)): path.read_bytes() for path in (clone / '.git/lfs').rglob('*') if path.is_file()}
        result = archive(clone, 'HEAD', self.root / 'snapshot', {'lfs': True, 'allow_network': True})
        self.assertEqual((self.root / 'snapshot/model.bin').read_bytes(), data)
        self.assertEqual(result[0]['sha256'], oid)
        self.assertEqual({str(path.relative_to(clone)): path.read_bytes() for path in (clone / '.git/lfs').rglob('*') if path.is_file()}, cached_before)
        self.assertEqual(self.git(clone, 'status', '--porcelain'), before)

    def test_escaping_symlink_is_rejected(self):
        (self.repo / 'escape').symlink_to('../../outside')
        self.git(self.repo, 'add', 'escape')
        self.git(self.repo, 'commit', '-qm', 'Add escaping symlink')
        with self.assertRaisesRegex(ValueError, 'escapes'):
            archive(self.repo, 'HEAD', self.root / 'snapshot', {'lfs': True, 'submodules': True})


if __name__ == '__main__':
    unittest.main()
