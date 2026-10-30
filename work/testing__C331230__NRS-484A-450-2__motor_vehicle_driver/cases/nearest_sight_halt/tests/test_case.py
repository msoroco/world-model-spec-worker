import unittest,tempfile
from pathlib import Path
from analyze import stop_before_crosswalk
from runner import check
class T(unittest.TestCase):
 def test_topology(self):self.assertTrue(check()['stop_approach_connected'])
 def test_missing(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(ValueError,'Missing required source: crosswalk_geometry.json'):stop_before_crosswalk(Path(t))

class SightSelection(unittest.TestCase):
 def test_select_closest_clear_sample_and_reject_all_blocked(self):
  import json
  from analyze import nearest_sight_samples
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'config.json').write_text(json.dumps({'stop_reference':'nearest_sight'}))
   samples=[{'candidate_eye_m':[x,1.75,1.5],'source_frame':21714,'rays':[{'clear':clear,'hits':[] if clear else [{'label':'obstruction'}]}]} for x,clear in [(-10,True),(-8,True),(-7.5,False)]]
   path=root/'sight_samples.json';path.write_text(json.dumps({'samples':samples,'resolution_m':.25,'scope':'test'}))
   self.assertEqual(nearest_sight_samples(root)['nearest_sampled_clear_eye_m'][0],-8)
   self.assertEqual(nearest_sight_samples(root)['source_frame'],21714)
   for s in samples:s['rays'][0]['clear']=False
   path.write_text(json.dumps({'samples':samples,'resolution_m':.25,'scope':'test'}))
   with self.assertRaisesRegex(ValueError,'No sampled clear'):nearest_sight_samples(root)
