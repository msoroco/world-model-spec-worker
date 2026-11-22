import importlib.util
from pathlib import Path
import unittest

FOLDER = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', FOLDER / 'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class MountedConstructionTests(unittest.TestCase):
    def test_reversal_stays_mounted(self):
        scene = runner.load_scene()
        self.assertFalse(scene['dismount_enabled'])
        points = runner.path_points(scene)
        self.assertFalse(points['afoot'])
        self.assertLess(points['mounted'][-1][0], scene['turn_x_m'])
        self.assertEqual(runner.phase_at(scene, scene['turn_x_m'], 0), 'mounted_reversal')


if __name__ == '__main__':
    unittest.main()
