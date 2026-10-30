import json,tempfile,unittest
from pathlib import Path
import analyze
class MeasurementTests(unittest.TestCase):
 def test_saved_entry_corner_and_simultaneity(self):
  def body(x,y):return [[x+a,y+b,z] for a in [-2,2] for b in [-1,1] for z in [0,2]]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'crosswalk_context.json').write_text(json.dumps({'band_xy_m':[-8.45,-7.05,-7,7],'intersection_xy_m':[-7,-7,7,7],'corner_xy_m':[-7,7]}))
   rows=[{'frame':i,'time_s':i*.05,'body_vertices_m':body(x,y),'heading_deg':180,'velocity_mps':[1,0,0],'reverse_control':True} for i,x,y in [(1,-12,1.75),(2,-7,1.75),(3,0,10)]]
   (p/'reverse_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   value=analyze.reverse_crosswalk_overlap(p)
   self.assertEqual(value['intersection_entry_transitions'][0]['entry_frame'],2)
   self.assertGreater(abs(value['street_corner_progression']['bearing_change_deg']),1)
   self.assertEqual(value['backing_overlap_original_frames'],[2])
   for r in rows:r['reverse_control']=False
   (p/'reverse_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   self.assertEqual(analyze.reverse_crosswalk_overlap(p)['backing_overlap_original_frames'],[])
   (p/'reverse_history.jsonl').unlink()
   with self.assertRaisesRegex(ValueError,'Missing required source: reverse_history.jsonl'):analyze.reverse_crosswalk_overlap(p)

import unittest

class StartupSettlingFallbackTest(unittest.TestCase):
    def test_stationary_native_warmup(self):
        import runner
        self.assertEqual(runner.startup_settling_ticks(), 40)
