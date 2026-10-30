"""Exact-ID v6 source-schema regressions; no actual recording or CARLA."""
import json,shutil,tempfile,unittest
from pathlib import Path
from analyze import CASE_ID,validate_identity,source_measurements
from diagnostic import HERE,ROOT,motion_sources
from worker_exchange.native_output import assess_left_turn

class LegacySourceTests(unittest.TestCase):
 def fixture(self,path,complete=True):
  shutil.copyfile(HERE/'config.json',path/'config.json');motion_sources(path,complete)
 def test_frozen_original_identity_and_proposal(self):
  contract=json.loads((ROOT/'inputs/legacy-captures/c109705-400-2a-selected-left-turn-v6.json').read_text())
  manifest=json.loads((HERE/'execution-manifest.json').read_text());proposal=json.loads((HERE/'proposals/cases.json').read_text())
  self.assertEqual([e['case_id'] for e in manifest['cases']],[CASE_ID]);self.assertEqual(manifest['cases'][0]['native_construction_sha256'],contract['original_construction_sha256']);self.assertEqual(proposal['cases'],[contract['original_case_proposal']])
 def test_900_complete_schema_and_source_checks(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);self.fixture(p);measure,sources,body,trace=source_measurements(p)
   self.assertEqual(measure['original_frames'],900);self.assertEqual(len(body),900);self.assertEqual(len(trace),900)
   self.assertTrue(all(len(h)==64 for h in sources.values()));self.assertEqual(assess_left_turn(p)['status'],'met')
 def test_900_incomplete_motion_is_not_complete(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);self.fixture(p,False);self.assertEqual(source_measurements(p)[0]['original_frames'],900);self.assertEqual(assess_left_turn(p)['status'],'not_met')
 def test_missing_motion_is_unverified(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);self.fixture(p);(p/'body_history.jsonl').unlink();self.assertEqual(assess_left_turn(p)['status'],'unverified')
   with self.assertRaisesRegex(ValueError,'Missing required source: body_history.jsonl'):source_measurements(p)
 def test_original_frame_identity_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);self.fixture(p);rows=[json.loads(s) for s in (p/'body_history.jsonl').read_text().splitlines()];rows[-1]['frame']=999999
   (p/'body_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaisesRegex(ValueError,'Original v6 frame join differs'):source_measurements(p)
 def test_no_v7_case_renaming(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);cfg=json.loads((HERE/'config.json').read_text());cfg['case']['case_id']=CASE_ID.replace('selected_left_turn','near_centerline');(p/'config.json').write_text(json.dumps(cfg))
   with self.assertRaisesRegex(ValueError,'Wrong retained v6 case identity'):validate_identity(p)

 def test_non_graph_fingerprint_mismatch_is_hard_failure(self):
  from unittest.mock import patch
  from analyze import FROZEN_SOURCES
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);self.fixture(p);(p/'construction.json').write_text(json.dumps({'case_id':CASE_ID}));(p/'capture').mkdir();(p/'capture/manifest.json').write_text(json.dumps({'case_id':CASE_ID}))
   # Isolate the body-file binding guard; no historical hash preimage is forged.
   with patch.dict(FROZEN_SOURCES,{'body_history.jsonl':'6e5170d738712807c3c964f28a13331c313e3b34ff26f8c1929f3856142ad071'},clear=True):
    with self.assertRaisesRegex(RuntimeError,'Frozen retained source hash differs: body_history.jsonl'):validate_identity(p)
