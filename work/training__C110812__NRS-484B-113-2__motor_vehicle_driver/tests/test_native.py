import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geometry import check,body,overlap,CROSSWALK,INTERSECTION
from controller import ReverseController,ReverseKnobs
from engineering import parameters,evaluate_trigger,TRIGGERS

class ReverseCornerUnit(unittest.TestCase):
 def test_authored_pair(self):
  outcomes=check()['cases']
  self.assertEqual(outcomes['condition_a']['heading_change_deg'],0)
  self.assertEqual(outcomes['condition_b']['heading_change_deg'],90)
  self.assertEqual(outcomes['condition_b']['max_crosswalk_overlap_m2'],0)
  self.assertGreater(outcomes['condition_a']['max_intersection_overlap_m2'],0)
  self.assertAlmostEqual(overlap(body(1.75,4.5,-90),INTERSECTION),11.22,places=1)
 def test_corner_controller(self):
  ctl=ReverseController('condition_b',ReverseKnobs())
  command=ctl.step(x_m=12,y_m=-1.75,heading_rad=0,signed_forward_speed_m_s=0)
  self.assertTrue(command['reverse'])
  self.assertGreater(command['requested_reverse_speed_m_s'],0)
 def test_three_distinct_fallbacks(self):
  base=parameters('condition_b','primary')['knobs']
  changed=[{key for key in base if base[key]!=parameters('condition_b',c)['knobs'][key]}
           for c in ('fallback1','fallback2','fallback3')]
  self.assertEqual(changed,[{'steering_gain'},{'brake_margin_m'},{'overview_fov_deg'}])
 def test_each_source_hashed_trigger_positive_negative(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'metrics.json'
   for candidate,trigger in TRIGGERS.items():
    for expected,value in ((True,trigger['threshold']+(1 if trigger['op']=='>' else -1)),
                           (False,trigger['threshold']+(-1 if trigger['op']=='>' else 1))):
     p.write_text(json.dumps({'source_kind':'original_native_and_video',trigger['metric']:value}))
     digest=hashlib.sha256(p.read_bytes()).hexdigest()
     self.assertIs(evaluate_trigger(candidate,p,digest),expected)
     with self.assertRaisesRegex(ValueError,'hash differs'):
      evaluate_trigger(candidate,p,'0'*64)
if __name__=='__main__':unittest.main()
