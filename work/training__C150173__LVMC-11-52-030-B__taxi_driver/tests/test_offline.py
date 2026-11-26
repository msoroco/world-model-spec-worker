import json
import unittest
from pathlib import Path
from runner import offline_check
from yellow_plan import check, read_requested

class TaxiYellowZone(unittest.TestCase):
 def test_exact_request(self):
  r=offline_check(Path('.'))
  self.assertEqual(r['frames'],600)
  self.assertFalse(r['sign_authority_verified'])
  self.assertEqual(r['request_measure']['requested_frames'],600)
 def test_missing_source(self):
  config=json.loads(Path('config.json').read_text())
  bad={**config,'sign_source_status':'verified_without_source'}
  with self.assertRaises(ValueError):check(bad,Path('yellow-road.xodr').read_text())
