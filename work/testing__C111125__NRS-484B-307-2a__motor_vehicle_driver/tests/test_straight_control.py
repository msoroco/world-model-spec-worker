import importlib.util
import unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'straight_control.py'
s=importlib.util.spec_from_file_location('straight_control',p);control=importlib.util.module_from_spec(s);s.loader.exec_module(control)
class ControlTests(unittest.TestCase):
    def setUp(self):
        self.site={'official_head_id':'h','ego_approach_id':'north','stop_line_xy':[0,0],'approach_control_radius_m':3,'approach_throttle':0.3,'yield_brake':0.7,'proceed_throttle':0.25}
        self.obs={'official_head_id':'h','facing_approach_id':'north','lit_aspects':['circular_green'],'frame':10,'ego_xy':[0,-1],'other_users':[{'region':'intersection'}]}
    def test_hold_for_original_occupied_zone(self):
        self.assertEqual(control.command(self.site,self.obs,'yield_to_present')['target'],'hold_before_entry')
        self.assertEqual(control.command(self.site,{**self.obs,'other_users':[]},'yield_to_present')['target'],'straight_route')
        self.assertEqual(control.command(self.site,{**self.obs,'ego_xy':[0,-10]},'yield_to_present')['target'],'approach')
    def test_reject_unbound_signal_and_missing_conflicts(self):
        with self.assertRaisesRegex(control.ControlError,'unbound'):
            control.command(self.site,{**self.obs,'official_head_id':'other'},'yield_to_present')
        with self.assertRaisesRegex(control.ControlError,'sole circular'):
            control.command(self.site,{**self.obs,'lit_aspects':['green_arrow']},'yield_to_present')
        with self.assertRaisesRegex(control.ControlError,'other-user packet'):
            control.command(self.site,{**self.obs,'other_users':None},'yield_to_present')
if __name__=='__main__':unittest.main()
