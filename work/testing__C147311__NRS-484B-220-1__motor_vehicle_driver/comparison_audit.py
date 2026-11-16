"""Independent saved-source audit for the controlled direction comparison."""
from pathlib import Path
import importlib.util


def _load_measurement():
 path=Path(__file__).with_name('one_way_measurements.py')
 spec=importlib.util.spec_from_file_location('one_way_measurements_for_audit',path)
 module=importlib.util.module_from_spec(spec)
 spec.loader.exec_module(module)
 return module


def audit(with_designation_root, against_designation_root):
 """Require identical road context and observed opposite travel, without a legal label."""
 measure=_load_measurement()
 with_result=measure.analyze(Path(with_designation_root))
 against_result=measure.analyze(Path(against_designation_root))
 if with_result['sources']['road_context.json']!=against_result['sources']['road_context.json']:
  raise ValueError('Comparison road context differs')
 for name,digest in with_result['sources'].items():
  if name in ('travel_history.jsonl','video_frames.jsonl','road_context.json'):
   continue
  if against_result['sources'].get(name)!=digest:
   raise ValueError('Comparison site source differs: '+name)
 for name in against_result['sources']:
  if name not in with_result['sources']:
   raise ValueError('Comparison site source differs: '+name)
 positive=with_result['samples'];negative=against_result['samples']
 if len(positive)!=len(negative):raise ValueError('Comparison frame counts differ')
 if [x['lane_id'] for x in positive]!=[x['lane_id'] for x in negative]:
  raise ValueError('Comparison selected lanes differ')
 if not all(x['complete_body_on_one_way_roadway'] for x in positive+negative):
  raise ValueError('Comparison body leaves sourced roadway')
 if not all(x['heading_alignment']>0 for x in positive):
  raise ValueError('With-designation heading not observed')
 if not all(x['heading_alignment']<0 for x in negative):
  raise ValueError('Against-designation heading not observed')
 if not all(step>0 for step in with_result['projected_step_m']):
  raise ValueError('With-designation displacement not observed')
 if not all(step<0 for step in against_result['projected_step_m']):
  raise ValueError('Against-designation displacement not observed')
 return {'format':'worker-one-way-comparison-audit',
         'road_context_sha256':with_result['sources']['road_context.json'],
         'with_sources':with_result['sources'],'against_sources':against_result['sources'],
         'frame_count':len(positive),'physical_acceptance':'unresolved',
         'legal_conclusion':'unresolved'}
