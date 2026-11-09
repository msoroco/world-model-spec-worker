"""Audited additive route-failure classification for retained native episodes.

Never edits original results or clears a flag. A receipt cannot turn a failed
attempt into accepted evidence; it only identifies the measured physical cause
of an incomplete maneuver in aggregate attempt history.
"""
import hashlib,json,math,runpy
from pathlib import Path

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def derive(directory):
 directory=Path(directory);result=json.loads((directory/'result.json').read_text());completion=result.get('completion',{});body={k:v for k,v in result.items() if k!='completion'}
 if hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest()!=completion.get('result_hash'):raise ValueError('Retained completion result changed')
 if result.get('maneuver_completed') is not False or result.get('termination_reason')!='incomplete_path':raise ValueError('Diagnosis requires retained incomplete route')
 refs=['trace.jsonl','scene_model.py','config.json','runner.py']
 for n in refs:
  if sha(directory/n)!=completion.get('artifact_hashes',{}).get(n):raise ValueError('Retained diagnosis source changed: '+n)
 construction=json.loads((directory/'construction.json').read_text());files={f['path']:f['content'] for f in construction['files']}
 for n in ('scene_model.py','config.json','runner.py'):
  if hashlib.sha256(files[n].encode()).hexdigest()!=sha(directory/n):raise ValueError('Diagnosis differs from executed construction')
 cfg=json.loads((directory/'config.json').read_text());model=runpy.run_path(str(directory/'scene_model.py'));paths={p['name']:p['points'] for p in model['phases'](cfg['maneuver_station'])};target=next(c for c in result['target_checks'] if c['target']=='commanded_turn_path');tolerance=target['tolerance']['path_tracking_m'];maximum=0.;count=0;first=None
 for line in (directory/'trace.jsonl').open():
  t=json.loads(line);packet=t['crest_reversal_native'];actor=packet['ego'];position=actor['position_m'];phase=packet['controller_inputs']['requested_path_phase'];points=paths[phase];error=min(math.hypot(p[0]-position[0],p[1]-position[1]) for p in points)
  if t['position_m']!=position or abs(error-packet['path_tracking_error_m'])>1e-7:raise ValueError('Route diagnosis contradicts original physical samples')
  if error>tolerance and first is None:first={'frame':t['frame'],'time_s':t['time_s'],'measured_error_m':error}
  maximum=max(maximum,error);count+=1
 if not first or maximum<=tolerance or abs(maximum-target['measured']['maximum_path_error_m'])>1e-7:raise ValueError('No measured route-tracking failure')
 return {'schema':'retained-route-failure-diagnosis-v1','original_directory':str(directory.resolve()),'result_sha256':sha(directory/'result.json'),'sources':{n:sha(directory/n) for n in refs},'measured_maximum_actor_centre_route_error_m':maximum,'unchanged_target_tolerance_m':tolerance,'original_frames':count,'first_out_of_tolerance':first,'additive_flags':{'route_tracking_failure':True},'policy':'Measured incomplete physical route only; original files unchanged, no collision/rollover inference, no acceptance or maneuver-completion change'}

def diagnosed_flags(directory):
 directory=Path(directory);path=directory/'physical_failure_diagnosis.json'
 if not path.exists():return None
 receipt=json.loads(path.read_text());actual=derive(directory)
 if receipt!=actual:raise ValueError('Retained failure diagnosis is stale or unsupported')
 return {'flags':actual['additive_flags'],'receipt':str(path),'sha256':sha(path),'measured_maximum_actor_centre_route_error_m':actual['measured_maximum_actor_centre_route_error_m']}
