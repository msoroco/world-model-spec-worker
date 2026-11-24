"""Synthetic source-joined travel outcomes and ownership event order."""
import hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
EVENTS=['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
manifest=json.loads((HERE/'execution-manifest.json').read_text())
for entry in manifest['cases']:
 witness=entry['case_id'].rsplit('__',1)[-1]
 source=HERE/'v2-primary'/witness/'sources'
 native=[json.loads(s) for s in (source/'native-raw-actors.jsonl').read_text().splitlines()]
 frame=[json.loads(s) for s in (source/'video_frames.jsonl').read_text().splitlines()]
 if len(native)!=600 or len(frame)!=600:raise ValueError('Synthetic frame count')
 for index,(actor,image) in enumerate(zip(native,frame)):
  if actor['frame']!=index or image['video_frame']!=index or actor['native_frame']!=image['carla_frame'] or abs(actor['time_s']-image['time_s'])>1e-8:raise ValueError('Synthetic source join')
 directory=HERE/'physical-proofs'/witness;fixtures=[]
 for kind in ('complete_motion','incomplete_motion','missing_evidence'):
  subset=native if kind=='complete_motion' else native[:10]
  joined=kind!='missing_evidence'
  start=subset[0]['ego']['center_native_xyz_m'];end=subset[-1]['ego']['center_native_xyz_m']
  progress=math.dist(start,end)
  status='unverified' if not joined else 'met' if progress>=50 else 'not_met'
  expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
  if status!=expected:raise ValueError('Diagnostic motion branch differs')
  result={'case_id':entry['case_id'],'construction_sha256':entry['construction_sha256'],
   'physical_checks':{'maneuver':{'status':status,
    'method':'source-joined synthetic ego body-center travel over observed frame window, 50 m engineering criterion',
    'sources':['native-raw-actors.jsonl','video_frames.jsonl']}},
   'maneuver_completed':status=='met',
   'realized_observables':{'ego_progress_m':round(progress,4)} if status=='met' else {},
   'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
   'original_native_motion_verified':False,'original_pixels_verified':False,'legal_verdict_claimed':False,
   'source_sha256':{'native-raw-actors.jsonl':sha(source/'native-raw-actors.jsonl'),
    'video_frames.jsonl':sha(source/'video_frames.jsonl')}}
  result_path=directory/(kind+'.json');log_path=directory/(kind+'.log')
  write(result_path,result)
  log_path.write_text(f'{entry["case_id"]} {kind} status={status} joined={joined} progress_m={progress:.4f} diagnostic=true\n')
  fixtures.append({'kind':kind,'command':f'.venv-cpu/bin/python work/{HERE.name}/prove-physical-branches.py',
   'exit_code':0,'log':str(log_path.relative_to(HERE)),'log_sha256':sha(log_path),
   'result':str(result_path.relative_to(HERE)),'result_sha256':sha(result_path)})
 lifecycle_log=directory/'lifecycle.log';lifecycle_log.write_text(' '.join(EVENTS)+'\n')
 proof_path=directory/'proof.json'
 write(proof_path,{'format':'c111603-synthetic-physical-branch-proof','case_id':entry['case_id'],
  'construction_sha256':entry['construction_sha256'],'fixtures_are_cpu_mocks':True,
  'original_native_motion_verified':False,'fixtures':fixtures,
  'lifecycle':{'events':EVENTS,'exit_code':0,'log':str(lifecycle_log.relative_to(HERE)),
   'log_sha256':sha(lifecycle_log)}})
 entry['physical_preparation']={'receipt':str(proof_path.relative_to(HERE)),'sha256':sha(proof_path)}
write(HERE/'execution-manifest.json',manifest)
print(json.dumps({'cases':len(manifest['cases']),'manifest_sha256':sha(HERE/'execution-manifest.json')}))
