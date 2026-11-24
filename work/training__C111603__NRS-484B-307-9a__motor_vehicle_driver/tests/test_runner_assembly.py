"""Original source assembly requires exact actor/camera identities."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
spec=importlib.util.spec_from_file_location('c111603_runner',HERE/'runner.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class OriginalAssembly(unittest.TestCase):
 def setUp(self):
  scratch=ROOT/'.runtime-work/c111603-source-shape-tests'
  scratch.mkdir(parents=True,exist_ok=True)
  self.temporary=tempfile.TemporaryDirectory(dir=scratch)
  self.addCleanup(self.temporary.cleanup)
  self.attempt=Path(self.temporary.name)
  self.bundle=HERE/'native/drafts/witness_1/primary'
  source=HERE/'v2-primary/witness_1/sources'
  for name in ('native-raw-actors.jsonl','video_frames.jsonl','native-map-readback.json','native-capture-report.json'):
   shutil.copy2(source/name,self.attempt/name)
  raw=runner.rows(self.attempt/'native-raw-actors.jsonl')
  for row in raw:
   row['source_kind']='original_native'
   row['weather_readback']={'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0}
  runner.write_rows(self.attempt/'native-raw-actors.jsonl',raw)
  mapping=json.loads((self.attempt/'native-map-readback.json').read_text())
  mapping['source_kind']='original_native'
  (self.attempt/'native-map-readback.json').write_text(json.dumps(mapping)+'\n')
  report=json.loads((self.attempt/'native-capture-report.json').read_text())
  report['error']=None; report['observed_frames']=600
  (self.attempt/'native-capture-report.json').write_text(json.dumps(report)+'\n')
  (self.attempt/'road.xodr').write_bytes((self.bundle/'arrow-intersection.xodr').read_bytes())
  construction=json.loads((HERE/'v2-primary/witness_1/construction.json').read_text())
  config=next(item['content'] for item in construction['files'] if item['path']=='config.json')
  (self.attempt/'config.json').write_text(config)
  (self.attempt/'capture').mkdir()
  (self.attempt/'capture/recorder_info.txt').write_text('Create 99: vehicle.tesla.model3\n')
 def test_complete_original_shaped_sources(self):
  self.assertEqual(runner.assemble(self.attempt,self.bundle)['frames'],600)
  self.assertEqual(len(runner.rows(self.attempt/'trace.jsonl')),600)
  self.assertEqual(len(runner.rows(self.attempt/'capture/native/frames.jsonl')),600)
  self.assertFalse(json.loads((self.attempt/'result.json').read_text())['maneuver_completed'])
 def test_missing_actor_source_rejected(self):
  (self.attempt/'native-raw-actors.jsonl').unlink()
  with self.assertRaises(FileNotFoundError):runner.assemble(self.attempt,self.bundle)
 def test_camera_identity_drift_rejected(self):
  video=runner.rows(self.attempt/'video_frames.jsonl')
  video[5]['carla_frame']+=1
  runner.write_rows(self.attempt/'video_frames.jsonl',video)
  with self.assertRaisesRegex(ValueError,'identities differ'):
   runner.assemble(self.attempt,self.bundle)

if __name__=='__main__':unittest.main()
