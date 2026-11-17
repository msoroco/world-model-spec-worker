import json, unittest
from pathlib import Path
import runner
class ExactCurbOffline(unittest.TestCase):
 def test_selected_case_and_independent_curb_targets(self):
  root=Path(__file__).resolve().parents[1]
  cfg=json.loads((root/'config.json').read_text())
  route=runner.check_native_config(cfg,root/'source_geometry.json')
  self.assertEqual(route['branch'],'approach_near_depart_near')
  self.assertEqual(route['approach']['left_curb_offset_setpoint_m'],.5)
  self.assertEqual(route['departure']['left_curb_offset_setpoint_m'],.5)
  self.assertFalse(route['actual_native_motion_verified'])
 def test_source_map_change_rejected(self):
  root=Path(__file__).resolve().parents[1]
  cfg=json.loads((root/'config.json').read_text())
  cfg['source_geometry_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'hash differs'):
   runner.check_native_config(cfg,root/'source_geometry.json')
