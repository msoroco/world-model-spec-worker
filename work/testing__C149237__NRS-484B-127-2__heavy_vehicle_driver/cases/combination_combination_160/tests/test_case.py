import tempfile,json,unittest
from pathlib import Path
import analyze
class TruckTests(unittest.TestCase):
 def test_all_unit_extrema(self):
  from following_controller import along_route_body_gap
  a=[[300+dx,dy,dz] for dx in [-5,5] for dy in [-1,1] for dz in [0,2]];b=[[470+dx,dy,dz] for dx in [-5,5] for dy in [-1,1] for dz in [0,2]]
  self.assertGreater(along_route_body_gap(a,b),152.4)
  self.assertLess(along_route_body_gap(a,b+a),0)
 def test_missing_history(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Missing required source: truck_history.jsonl'):analyze.body_gap(Path(d))
