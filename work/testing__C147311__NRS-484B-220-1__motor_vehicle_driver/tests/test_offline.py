import json,unittest
from pathlib import Path
from types import SimpleNamespace as NS
import runner
class Offline(unittest.TestCase):
 def test_source_join_and_case(self):
  root=Path(__file__).resolve().parents[1];cfg=runner.validate_config(json.loads((root/'config.json').read_text()));packet=json.loads((root/'site_packet.json').read_text())
  def wp(lane,x,y):return NS(road_id=5,lane_id=lane,lane_type='Driving',transform=NS(location=NS(x=x,y=y)))
  points=[wp(lane,x,y) for lane,y in ((-1,-1.75),(-2,-5.25)) for x in (0,10,20,30)]
  world=NS(get_map=lambda:NS(name='TownX',generate_waypoints=lambda spacing:points))
  prepared,route=runner.prepare_site(world,packet,root,cfg)
  self.assertEqual(route[0],[0.0,-1.75]);self.assertEqual(route[-1],[30.0,-1.75]);self.assertEqual(prepared['site_review']['physical_sign_visibility'],'unverified')
if __name__=='__main__':unittest.main()
