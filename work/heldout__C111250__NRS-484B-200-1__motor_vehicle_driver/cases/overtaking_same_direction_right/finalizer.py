"""C111250 passing-premise saved-source finalizer; no physical or legal verdict."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from delivery_audit import CAMERAS,audit_delivery

CHANNELS=('full_body_leftward_clearance_m','any_left_half_body','exception_source_context')
REQUIRED=('road_geometry.json','exception_context.json','body_history.jsonl','video_frames.jsonl',
          'trace.jsonl','passed_vehicle_original.json','passed_vehicle_history.jsonl',*(camera+'.mkv' for camera in CAMERAS),
          *(camera+'-frames.jsonl' for camera in CAMERAS))

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def finalize(attempt):
 root=Path(attempt)
 for name in REQUIRED:
  if not (root/name).is_file():raise ValueError('Missing required source: '+name)
 cfg=json.loads((root/'config.json').read_text())
 rows=[json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines() if line.strip()]
 audit=audit_delivery(root,expected_frames=len(rows))
 measured=audit['case_measurement']
 road=json.loads((root/'road_geometry.json').read_text())
 passed=[json.loads(line) for line in (root/'passed_vehicle_history.jsonl').read_text().splitlines() if line.strip()]
 if len(passed)!=len(rows) or any(p.get('frame')!=m.get('carla_frame') or p.get('time_s')!=m.get('time_s') for p,m in zip(passed,rows)):
  raise ValueError('Original passed vehicle/body frame join failed')
 def centroid(row):
  points=row.get('ground_corners')
  if not isinstance(points,list) or len(points)!=4 or any(not isinstance(point,list) or len(point)!=2 for point in points):
   raise ValueError('Original passed vehicle corners incomplete')
  return (sum(point[0] for point in points)/4,sum(point[1] for point in points)/4)
 first,last=centroid(passed[0]),centroid(passed[-1])
 a,b=road['centerline'];dx,dy=b[0]-a[0],b[1]-a[1];distance=(dx*dx+dy*dy)**.5
 if distance<=0:raise ValueError('Original road direction missing')
 passed_progress=((last[0]-first[0])*dx+(last[1]-first[1])*dy)/distance
 if passed_progress<=0:raise ValueError('Original passed vehicle did not proceed in road direction')
 if len(measured['samples'])!=len(rows):raise ValueError('Original road-half body inventory differs')
 values={name:[] for name in CHANNELS}
 for sample,time_s,frame in zip(measured['samples'],measured['original_times_s'],measured['original_frames']):
  shared={'frame':frame,'time_s':time_s}
  values['full_body_leftward_clearance_m'].append(dict(shared,value=sample['max_leftward_m']))
  values['any_left_half_body'].append(dict(shared,value=sample['any_left_half_body']))
  values['exception_source_context'].append(dict(shared,value={'exception':measured['exception'],
   'road_source_sha256':measured['source_sha256']['road_geometry.json'],
   'passed_vehicle_source_sha256':measured['source_sha256']['passed_vehicle_original.json'],
   'passed_same_direction_progress_m':passed_progress,
   'legal_exception_judgment':None}))
 for name,stream in values.items():
  path=root/(name+'.jsonl')
  if path.exists():raise ValueError('Retain existing derived channel: '+name)
  path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in stream))
 source_hashes={name:_sha(root/name) for name in REQUIRED}
 report={'format':'worker-analysis-report','case_id':cfg['selected_case_id'],
         'measurements':{name:{'method':'finalize','value':stream,'sources':source_hashes}
                         for name,stream in values.items()},
         'original_frame_count':len(rows),'any_left_half_body':measured['any_left_half_body'],
         'legal_exception_judgment':None,'physical_acceptance_claimed':False,
         'limitations':['Original-source software measurement only; actual road, motion and camera pixels require Native review']}
 description=cfg['case']['recording_description']
 units={channel['name']:channel['unit'] for channel in description['channels']}
 if set(units)!=set(CHANNELS):raise ValueError('Exact recording channel description differs')
 evidence=[{'name':name,'unit':units[name],'reference':name+'.jsonl','sha256':_sha(root/(name+'.jsonl'))}
           for name in CHANNELS]
 result={'case_id':cfg['selected_case_id'],'measured_values':{name:len(stream) for name,stream in values.items()},
   'target_checks':[{'target':'original right-half occupancy','requested':'full body on right half through source-scoped frames',
     'measured':measured['any_left_half_body'],'method':'source-joined original body corners versus oriented centerline',
     'tolerance':None,'matched':False,'physical_cause_confirmed':False,
     'cause_evidence':'Actual Native scene and legal applicability unverified'}],
   'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
   'termination_reason':'Original road-half evidence measured; physical and legal judgment open',
   'physical_failure_flags':{'visibility_validated':False,'road_feature_validated':False},
   'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],
   'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
   'recording_evidence':evidence,'realized_observables':{name:{'unit':units[name],
      'method':'original source/frame join','time_window':'original recorded interval','statistic':'sample count',
      'reference':name+'.jsonl','value':len(stream),'sample_window_s':[stream[0]['time_s'],stream[-1]['time_s']]}
      for name,stream in values.items()},
   'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
 return report,result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
 args=parser.parse_args();output=Path(args.output)
 if output.exists():raise ValueError('Retain prior analysis report')
 report,result=finalize(args.attempt)
 output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
 from worker_exchange.native_output import write_result
 write_result(args.attempt,result)

if __name__=='__main__':main()
