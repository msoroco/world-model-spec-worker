import importlib.util
import unittest
from pathlib import Path
MODULE=Path(__file__).resolve().parents[1]/'comparison_audit.py'
spec=importlib.util.spec_from_file_location('comparison_audit_c109171',MODULE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def result(case,walk,entry):
 return {'case_suffix':case,'map_source_sha256':'a','vehicle_signal_source_sha256':'b',
 'highway_boundary_source_sha256':'c','pedestrian_route_source_sha256':'d',
 'camera_profile_sha256':'e','duration_frames':600,'sole_green_arrow_frames':600,
 'first_highway_entry':{'frame':200,'separate_walk_indication':walk} if entry else None,
 'separate_walk_indication_without_entry':walk}
class ComparisonTest(unittest.TestCase):
 def test_three_pairs(self):
  pairs=[('entry_without_other_permission',result('arrow_wait',False,False),result('arrow_early_entry',False,True)),('separate_device_permission',result('arrow_early_entry',False,True),result('arrow_walk_entry',True,True)),('permitted_entry_choice',result('arrow_walk_wait',True,False),result('arrow_walk_entry',True,True))]
  for name,l,r in pairs:
   self.assertEqual(mod.audit_pair(name,l,r)['physical_acceptance'],False)
 def test_reject_changed_map(self):
  l=result('arrow_wait',False,False);r=result('arrow_early_entry',False,True);r['map_source_sha256']='changed'
  with self.assertRaisesRegex(mod.ComparisonError,'map_source'):mod.audit_pair('entry_without_other_permission',l,r)
 def test_reject_unrealized_entry(self):
  with self.assertRaisesRegex(mod.ComparisonError,'not realized'):mod.audit_pair('entry_without_other_permission',result('arrow_wait',False,False),result('arrow_early_entry',False,False))
 def test_reject_wrong_permission(self):
  with self.assertRaisesRegex(mod.ComparisonError,'device state'):mod.audit_pair('separate_device_permission',result('arrow_early_entry',False,True),result('arrow_walk_entry',False,True))
 def test_reject_arrow_not_sole(self):
  l=result('arrow_wait',False,False);l['sole_green_arrow_frames']=599
  with self.assertRaisesRegex(mod.ComparisonError,'sole green'):mod.audit_pair('entry_without_other_permission',l,result('arrow_early_entry',False,True))
if __name__=='__main__':unittest.main()
