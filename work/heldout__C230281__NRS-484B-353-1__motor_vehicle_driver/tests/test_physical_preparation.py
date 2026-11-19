from __future__ import annotations
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

class PhysicalPreparationTests(unittest.TestCase):
 def test_school_bus_exact_physical_checker_separates_progress_from_legal_premises(self):
  import json
  package=Path(__file__).resolve().parents[1]
  root=package.parents[1]
  sys.path.insert(0,str(root/'runtime'))
  from scenario_pipeline.worker_exchange.native_output import assess_physical
  manifest=json.loads((package/'execution-manifest.json').read_text())
  for entry in manifest['cases']:
   with self.subTest(case=entry['case_id']):
    construction=json.loads((package/entry['construction']).read_text())
    config=json.loads(next(item['content'] for item in construction['files']
                           if item['path']=='config.json'))
    count=round(float(config['duration_s'])*float(config['rate_hz']))
    self.assertEqual(count,160)
    with TemporaryDirectory() as temp:
     path=Path(temp)
     (path/'config.json').write_text(json.dumps(config)+'\n')
     frames=[{'carla_frame':1000+i,'time_s':i/20} for i in range(count)]
     (path/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
     def trace(distance):
      rows=[{'frame':1000+i,'time_s':i/20,
             'position_m':[distance*i/(count-1),0.0]} for i in range(count)]
      (path/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
     trace(24.0)
     complete=assess_physical(path,config)
     self.assertEqual(complete['physical_checks']['setup']['status'],'met')
     self.assertEqual(complete['physical_checks']['maneuver']['status'],'met')
     self.assertEqual(complete['physical_checks']['target']['status'],'unverified')
     self.assertFalse(complete['physical_checks']['maneuver']['legal_verdict_claimed'])
     self.assertFalse(complete['physical_checks']['maneuver']['legal_verdict_claimed'])
     trace(0.1)
     incomplete=assess_physical(path,config)
     self.assertEqual(incomplete['physical_checks']['maneuver']['status'],'not_met')
     (path/'trace.jsonl').unlink()
     missing=assess_physical(path,config)
     self.assertEqual(missing['physical_checks']['maneuver']['status'],'unverified')
     self.assertIn('trace.jsonl',missing['physical_checks']['maneuver']['missing_evidence'])


def physical_fixture(case_id, kind):
 import json
 package=Path(__file__).resolve().parents[1]
 root=package.parents[1]
 sys.path.insert(0,str(root/'runtime'))
 from scenario_pipeline.worker_exchange.native_output import assess_physical
 from scenario_pipeline.worker_exchange.common import sha
 manifest=json.loads((package/'execution-manifest.json').read_text())
 entry=next((e for e in manifest['cases'] if e['case_id']==case_id),None)
 if entry is None: raise ValueError('Unknown exact C230281 case')
 if kind not in ('complete_motion','incomplete_motion','missing_evidence'):
  raise ValueError('Unknown physical fixture outcome')
 construction=json.loads((package/entry['construction']).read_text())
 config=json.loads(next(item['content'] for item in construction['files']
                        if item['path']=='config.json'))
 count=round(float(config['duration_s'])*float(config['rate_hz']))
 with TemporaryDirectory(prefix='c230281-physical-',dir=root/'.runtime-work') as temp:
  path=Path(temp)
  (path/'config.json').write_text(json.dumps(config,sort_keys=True)+'\n')
  frames=[{'carla_frame':1000+i,'time_s':i/float(config['rate_hz'])} for i in range(count)]
  (path/'video_frames.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in frames))
  if kind!='missing_evidence':
   distance=24.0 if kind=='complete_motion' else 0.1
   rows=[{'frame':1000+i,'time_s':i/float(config['rate_hz']),
          'position_m':[distance*i/(count-1),0.0]} for i in range(count)]
   (path/'trace.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
  assessed=assess_physical(path,config)
  expected={'complete_motion':'met','incomplete_motion':'not_met',
            'missing_evidence':'unverified'}[kind]
  if assessed['physical_checks']['maneuver']['status']!=expected:
   raise AssertionError('Unexpected exact physical fixture outcome')
  return {'case_id':case_id,'construction_sha256':sha(package/entry['construction']),
          'fixture_kind':kind,'provenance_kind':'synthetic_fixture',
          'diagnostic_fixture':True,'actual_native_capture':False,
          'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
          **assessed}


def lifecycle_fixture():
 events=['capture_finished','encoders_closed','restoration_verified',
         'native_exit','owner_released','saved_processing_started']
 premature=events.copy();premature[3],premature[4]=premature[4],premature[3]
 def valid(rows):
  return rows.index('capture_finished')<rows.index('encoders_closed')<rows.index('restoration_verified')<rows.index('native_exit')<rows.index('owner_released')<rows.index('saved_processing_started')
 if not valid(events) or valid(premature): raise AssertionError('Early owner release accepted')
 return {'events':events,'provenance_kind':'synthetic_fixture',
         'early_owner_release_rejected':True}


if __name__=='__main__':
 import argparse,json
 parser=argparse.ArgumentParser()
 parser.add_argument('--case')
 parser.add_argument('--kind',required=True,
                     choices=('complete_motion','incomplete_motion','missing_evidence','lifecycle'))
 args=parser.parse_args()
 if args.kind=='lifecycle': result=lifecycle_fixture()
 else:
  if not args.case: raise ValueError('Exact case required')
  result=physical_fixture(args.case,args.kind)
 print(json.dumps(result,sort_keys=True))
