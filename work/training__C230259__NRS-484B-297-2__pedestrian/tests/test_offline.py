import copy
import json
import unittest
from pathlib import Path
from runner import check, _packet

class ExactDraft(unittest.TestCase):
 def setUp(self): self.config=json.loads(Path('config.json').read_text())
 def test_contract(self):
  receipt=check(self.config)
  self.assertEqual(receipt['frames'],600)
  self.assertFalse(receipt['physical_completion'])
  self.assertFalse(receipt['carla_contacted'])
 def test_negative(self):
  for key,value in [('frames',599),('actor','driver'),('physical_completion',True),('source_packet_required',False)]:
   bad=copy.deepcopy(self.config);bad[key]=value
   with self.assertRaises(ValueError):check(bad)
 def test_no_unsourced_native(self):
  with self.assertRaises(FileNotFoundError):_packet('missing-original-source.json',self.config)
