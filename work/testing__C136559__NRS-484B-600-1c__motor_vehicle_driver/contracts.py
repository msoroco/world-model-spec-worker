"""Strict retained-output validation. No simulator import and no legal judgment."""
import json,math,pathlib,hashlib
from worker_exchange.runtime_contract import validate_result,channel_samples,route_contained

def rows(path):
 with pathlib.Path(path).open() as f:return [json.loads(line) for line in f if line.strip()]

def contained(root,name):
 root=pathlib.Path(root).resolve();p=(root/name).resolve()
 if root not in p.parents or not p.is_file():raise ValueError('Missing contained evidence: '+str(name))
 return p

def validate_output(directory,result,requirements):
 root=pathlib.Path(directory);validate_result(root,result)
 trace=rows(contained(root,result['trace_reference']));mapping=rows(contained(root,result['video_frame_map_reference']))
 if not trace or len(trace)!=len(mapping):raise ValueError('Trace/video count mismatch')
 for i,(t,m) in enumerate(zip(trace,mapping)):
  if m.get('video_frame')!=i or m.get('carla_frame')!=t.get('frame') or m.get('time_s')!=t.get('time_s'):raise ValueError('Original frame/timestamp mismatch')
  if not isinstance(t.get('time_s'),(int,float)) or not math.isfinite(t['time_s']):raise ValueError('Invalid original timestamp')
  if i and t['time_s']<=trace[i-1]['time_s']:raise ValueError('Nonincreasing trace timestamps')
  if not all(k in t for k in ('position','heading_deg','speed_mps')):raise ValueError('Incomplete original telemetry')
 evidence={e['name']:e for e in result.get('recording_evidence',[])}
 for c in requirements['channels']:
  name=c['name']
  if name not in evidence:raise ValueError('Missing mandatory channel '+name)
  stream=rows(contained(root,evidence[name]['reference']));channel_samples(stream,len(trace))
  if any(s['time_s']!=t['time_s'] for s,t in zip(stream,trace)):raise ValueError('Channel timestamp mismatch '+name)
  dt=1/c['sampling_rate_hz']
  if any(abs(b['time_s']-a['time_s']-dt)>1e-5 for a,b in zip(stream,stream[1:])):raise ValueError('Channel rate mismatch '+name)
 for check in result['target_checks']:
  for key in ('target','requested','measured','method','tolerance','matched','physical_cause_confirmed','cause_evidence'):
   if key not in check:raise ValueError('Incomplete measured target '+key)
  if check['measured'] is None or check['matched'] is not True or check['physical_cause_confirmed'] is not True:raise ValueError('Unconfirmed measured target')
  if isinstance(check['measured'],float) and not math.isfinite(check['measured']):raise ValueError('Nonfinite measured target')
  if not check['method'] or not check['cause_evidence']:raise ValueError('Missing measurement provenance')
  refs=check['cause_evidence'] if isinstance(check['cause_evidence'],list) else [check['cause_evidence']]
  for ref in refs:contained(root,ref)
 for name in result['video_references']:
  video=contained(root,name)
  with video.open('rb') as f:header=f.read(64)
  if b'ftyp' not in header and not header.startswith(bytes.fromhex('1a45dfa3')):raise ValueError('Encoded video container required; PNG paths are invalid')
  inspect_video(video,len(trace))
 for name,definition in result.get('realized_observables',{}).items():
  raw=rows(contained(root,definition['reference']));window=definition.get('sample_window_s')
  if not window or len(window)!=2:raise ValueError('Missing actual summary sample window')
  data=[s['value'] for s in raw if window[0]<=s['time_s']<=window[1]]
  if not data:raise ValueError('Empty summary window')
  stat=definition['statistic'];actual=sum(data)/len(data) if stat=='mean' else min(data) if stat=='min' else max(data) if stat=='max' else None
  if actual is None or not math.isclose(actual,definition['value'],rel_tol=1e-9,abs_tol=1e-9):raise ValueError('Summary not recomputable from original samples')
 for context in requirements.get('context_inputs',[]):
  name=context['name']
  if name not in evidence:raise ValueError('Missing authored context '+name)
  value=json.loads(contained(root,evidence[name]['reference']).read_text())
  if name not in value or value[name] is None:raise ValueError('Unavailable authored context '+name)
 if result.get('required_participant_ids'):
  history=rows(contained(root,result['participant_history_reference']))
  if len(history)!=len(trace):raise ValueError('Incomplete participant history')
  required=set(result['required_participant_ids'])
  for h,t in zip(history,trace):
   if h['time_s']!=t['time_s'] or not required<={p['actor_id'] for p in h['participants']}:raise ValueError('Missing required participant in original frame')
 if result.get('footprint_reference'):
  history=rows(contained(root,result['footprint_reference']));polygons=result['driving_polygons']
  if len(history)!=len(trace):raise ValueError('Incomplete footprint history')
  for sample in history:
   for vertex in sample['vertices']:
    if not any(_inside(vertex[:2],polygon) for polygon in polygons):raise ValueError('Route/body footprint outside authored surface')
 return True

def _inside(vertex,polygon):
 try:route_contained([vertex],polygon);return True
 except ValueError:return False

def measured_target(name,requested,measured,tolerance,method,evidence,physical=True):
 if isinstance(requested,(int,float)) and not isinstance(requested,bool):matched=measured is not None and abs(measured-requested)<=tolerance
 else:matched=measured==requested
 return dict(target=name,requested=requested,measured=measured,tolerance=tolerance,method=method,matched=bool(matched),physical_cause_confirmed=bool(physical),cause_evidence=evidence)

def summarize(samples,start,end,statistic='mean'):
 selected=[s for s in samples if start<=s['time_s']<=end]
 if not selected:raise ValueError('No actual samples in declared window')
 values=[s['value'] for s in selected]
 if any(v is None for v in values):raise ValueError('Missing actual measurement')
 value=sum(values)/len(values) if statistic=='mean' else min(values) if statistic=='min' else max(values) if statistic=='max' else None
 if value is None:raise ValueError('Unsupported statistic')
 return value,[selected[0]['time_s'],selected[-1]['time_s']]

def inspect_video(path,expected_frames,hz=20):
 import subprocess
 p=subprocess.run(['ffprobe','-v','error','-count_frames','-show_entries','stream=nb_read_frames,avg_frame_rate','-of','json',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 if p.returncode:raise ValueError('Encoded video cannot be decoded')
 streams=json.loads(p.stdout).get('streams',[])
 if not streams or int(streams[0].get('nb_read_frames',-1))!=expected_frames:raise ValueError('Encoded video/trace frame count mismatch')
 numerator,denominator=map(float,streams[0]['avg_frame_rate'].split('/'))
 if not denominator or abs(numerator/denominator-hz)>1e-6:raise ValueError('Encoded video rate mismatch')
 return True
