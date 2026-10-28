import sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import crossing
class Crossing(unittest.TestCase):
 def test_connected_crossings_are_separate(self):
  root=ET.fromstring(crossing.build_crossing());self.assertEqual(len(root.findall('junction')),2)
  roads={r.attrib['id'] for r in root.findall('road')}
  for c in root.findall('junction/connection'):
   self.assertIn(c.attrib['incomingRoad'],roads);self.assertIn(c.attrib['connectingRoad'],roads)
 def test_order_brackets_do_not_invent_equality(self):
  rows=[]
  for t,e,o in [(0,False,False),(1,False,True),(2,True,True),(3,True,False)]:rows.append({'time_s':t,'ego':{'inside':e},'other':{'inside':o}})
  result=crossing.finalization(rows,{})
  self.assertFalse(result['other_entry_precedes_ego']);self.assertFalse(result['ego_enters_after_other_clears'])
 def test_yield_controller_branch(self):
  self.assertEqual(crossing.yield_target('prior_entry_yield',True,True,190),0)
  self.assertEqual(crossing.yield_target('prior_entry_no_yield',True,True,190),8)
