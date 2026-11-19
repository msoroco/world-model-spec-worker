import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pathing import repository_root


class PathingTest(unittest.TestCase):
    def test_package_and_materialized_paths_find_same_checkout(self):
        package = Path(__file__).resolve()
        root = repository_root(package)
        materialized = root/'.runtime-work/c183370/offline/runner.py'
        self.assertEqual(repository_root(materialized), root)

    def test_unrelated_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'outside a worker repository'):
            repository_root('/tmp/unrelated-worker-root/native/capture.py')


if __name__=='__main__':
    unittest.main()
