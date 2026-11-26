import copy
import json
import unittest
from pathlib import Path
from runner import check
class DraftContract(unittest.TestCase):
    def setUp(self):self.c=json.loads(Path("config.json").read_text())
    def test_window(self):self.assertEqual(check(self.c)["frames"],600)
    def test_missing_camera(self):
        c=copy.deepcopy(self.c);c["cameras"].pop()
        with self.assertRaisesRegex(ValueError,"Four cameras"):check(c)
    def test_short_window(self):
        c=copy.deepcopy(self.c);c["duration_frames"]=599
        with self.assertRaisesRegex(ValueError,"Full window"):check(c)
    def test_changed_distance(self):
        c=copy.deepcopy(self.c);c["signal_distance_m"]+=1
        with self.assertRaisesRegex(ValueError,"Signal-distance"):check(c)
    def test_wrong_district(self):
        c=copy.deepcopy(self.c);c["layout"]="other_area"
        with self.assertRaisesRegex(ValueError,"Fixed scene"):check(c)
