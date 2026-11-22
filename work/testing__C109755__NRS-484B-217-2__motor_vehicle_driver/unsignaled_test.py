import importlib.util
from pathlib import Path
import unittest
FOLDER=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('runner',FOLDER/'runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class VariantTests(unittest.TestCase):
 def test_crossing_is_unsignaled(self):
  scene=runner.load_scene();self.assertFalse(scene['signal_enabled'])
  self.assertTrue(runner.crosses_stripe(scene))
  self.assertFalse(runner.controller_command(scene,scene['crossing_x_m'],True)['left_signal'])
if __name__=='__main__':unittest.main()
