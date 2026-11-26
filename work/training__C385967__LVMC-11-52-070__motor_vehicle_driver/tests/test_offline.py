import copy
import json
import unittest
from pathlib import Path
from selected_runner import check
class ExactAnglePark(unittest.TestCase):
 def setUp(self): self.c=json.loads(Path('config.json').read_text())
 def test_selected(self): self.assertEqual(check(self.c)['frames'],600)
 def test_short(self):
  c=copy.deepcopy(self.c);c['duration_frames']=599
  with self.assertRaises(ValueError):check(c)
 def test_missing_permission(self):
  c=copy.deepcopy(self.c);c['permission_source_required']=False
  with self.assertRaises(ValueError):check(c)
 def test_wrong_orientation(self):
  c=copy.deepcopy(self.c);c['requested_front_yaw_deg']+=180
  with self.assertRaises(ValueError):check(c)
