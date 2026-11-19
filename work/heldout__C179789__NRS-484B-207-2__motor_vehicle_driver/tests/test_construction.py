import json, unittest
from pathlib import Path
from overtaken_native import check_plan, PREFIX, readback
from overtaken_controller import CASES, target, feedback
class Construction(unittest.TestCase):
 def test_all_exact_bindings(self):
  plan=json.loads(Path("case-plan.json").read_text())
  for suffix in CASES: self.assertEqual(check_plan(plan,PREFIX+suffix),suffix)
  with self.assertRaises(ValueError): check_plan(plan,PREFIX+"invented")
 def test_control_and_source_contract(self):
  plan=target("gives_way_holds_speed",notice_kind="audible_signal",notice_source="scripted construction stimulus",pass_complete=False)
  self.assertLess(feedback(plan,right_offset_m=0,speed_mps=4)["steer"],0)
  self.assertIsNone(plan["legal_conclusion"])
