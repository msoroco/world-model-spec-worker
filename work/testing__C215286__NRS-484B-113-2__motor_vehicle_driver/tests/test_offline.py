import json,unittest
from pathlib import Path
import runner
class Offline(unittest.TestCase):
 def test_source_join_and_case(self):
  root=Path(__file__).resolve().parents[1]
  cfg=runner.validate_config(json.loads((root/'config.json').read_text()))
  packet=json.loads((root/'site_packet.json').read_text())
  review,start,forward,target=runner.prepare_site(packet,root,cfg)
  self.assertEqual(target,6.0)
  self.assertEqual(review['targets']['short_distance_m'],2.0)
  self.assertEqual(review['site_review']['marked_crosswalk_visibility'],'unverified')
if __name__=='__main__':unittest.main()
