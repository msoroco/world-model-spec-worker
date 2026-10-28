import sys,unittest,math,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maneuvers
class ManeuverGeometry(unittest.TestCase):
 def test_uturn_centerline_continuity(self):
  route=maneuvers.uturn_route();self.assertLess(max(math.dist(a,b) for a,b in zip(route,route[1:])),2.1)
  self.assertAlmostEqual(route[-1][1],23.5);self.assertEqual(len(ET.fromstring(maneuvers.build_uturn()).findall('road')),3)
 def test_rotated_polygon_separation(self):
  vehicle=[(0,1),(1,0),(0,-1),(-1,0)];self.assertTrue(maneuvers.polygons_overlap(vehicle,[(.5,.5),(2,.5),(2,2),(.5,2)]));self.assertFalse(maneuvers.polygons_overlap(vehicle,[(2,2),(3,2),(3,3),(2,3)]))
