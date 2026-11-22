import json,hashlib,os,subprocess,shutil,copy,sys
from pathlib import Path
p=Path('work/testing__C125763__NRS-484B-250-1__motor_vehicle_driver');w=Path('.runtime-work/c125763-next');m=json.loads((p/'execution-manifest.json').read_text());c=m['cases'][-1];case=c['case_id']
env=os.environ.copy();env['SCENARIO_PIPELINE_OUTPUT_ROOT']=str(w/'runtime');env['PYTHONDONTWRITEBYTECODE']='1'
candidate=sys.argv[1] if len(sys.argv)>1 else 'primary'
if candidate not in ('primary','fallback1','fallback2','fallback3'):raise ValueError('Unknown candidate')
a=w/'saved-900-attempt'/candidate;a.parent.mkdir(parents=True,exist_ok=True)
cmd=['.venv-cpu/bin/python','runtime.py','materialize','--manifest',str(p/'execution-manifest.json'),'--case',case,'--output',str(a)]
if candidate!='primary':cmd+=['--candidate',candidate]
if not a.exists():
 r=subprocess.run(cmd,env=env,text=True,capture_output=True)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
s=w/'compat-opposite-900'/candidate
exclude={'channels','converted','result.json','analysis-report.json','compatibility.json','compatibility-analysis.log','negative-analysis.log','event_review.webm','event_review.json','event_review_frames.jsonl','event_review_encoder.log','candidate-selection.json','construction.json','config.json','four-view-receipt.json','raw.mkv'}
for f in s.rglob('*'):
 if not f.is_file():continue
 rel=f.relative_to(s)
 if any(part in exclude for part in rel.parts) or f.name.endswith('.log') or f.suffix=='.mkv':continue
 dest=a/rel
 if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);os.link(f,dest)
print('copied original 60-frame fixture',flush=True)
# Expand the synthetic source time base. All appended records are synthetic diagnostic data.
for name in ('crossing_history.jsonl','controller_history.jsonl','video_frames.jsonl','trace.jsonl','capture/evidence.jsonl','capture/native/frames.jsonl'):
 f=a/name;rows=[json.loads(x) for x in f.read_text().splitlines()];assert len(rows)==60
 result=rows[:]
 for i in range(60,900):
  row=copy.deepcopy(rows[-1]);frame=100+i;time=round(i/20,2)
  for key in ('frame','original_frame','replay_frame','carla_frame','native_frame'):
   if key in row:row[key]=frame
  for key in ('time_s','recording_time_s','replay_simulation_time_s','simulation_time'):
   if key in row:row[key]=time
  if 'video_frame' in row:row['video_frame']=i
  if name=='capture/evidence.jsonl':
   row['original_observations']['frame']=frame;row['original_observations']['time_s']=time
  if name=='capture/native/frames.jsonl':
   for key in ('abstract','base','adapter_graph'):
    if key in row:row[key]=row[key].replace('00000159',f'{frame:08d}')
  result.append(row)
 f.unlink();f.write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in result))
 print(name,len(result),flush=True)
for kind in ('base','abstract'):
 src=a/f'capture/native/graphs/{kind}/00000159.adapter.json';d=json.loads(src.read_text())
 for i in range(60,900):
  frame=100+i;time=round(i/20,2);out=src.parent/f'{frame:08d}.adapter.json';row=copy.deepcopy(d)
  if 'metadata' in row:
   row['metadata']['frame']=frame;row['metadata']['simulation_time_s']=time
   if kind=='base' and 'observed_evidence' in row['metadata']:
    row['metadata']['observed_evidence']['frame']=frame
    row['metadata']['observed_evidence']['time_s']=time
  out.write_text(json.dumps(row,allow_nan=False)+'\n')
 print('graphs',kind,900,flush=True)
manifest=a/'capture/manifest.json';d=json.loads(manifest.read_text());d['frames']=900;d['source_run']='fixture:900-synthetic-original-frame-extension';d['sources']['trace.jsonl']=hashlib.sha256((a/'trace.jsonl').read_bytes()).hexdigest();manifest.unlink();manifest.write_text(json.dumps(d,indent=2)+'\n')
for name in ('overview','approach','reference_corner','driver_reference'):
 src=s/(name+'.mkv');out=a/(name+'.mkv')
 if not out.exists():
  cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-stream_loop','14','-i',str(src),'-c','copy',str(out)]
  r=subprocess.run(cmd,text=True,capture_output=True)
  if r.returncode:raise RuntimeError(r.stderr)
 print('video',name,out.stat().st_size,flush=True)
print('900 source fixture built',flush=True)
