"""Validate original retained capture. Unknown observations are explicit failures."""
import json,pathlib,argparse,hashlib

def rows(p):
 with p.open() as f:return [json.loads(line) for line in f if line.strip()]

def validate(root,recording):
 root=pathlib.Path(root);issues=[];hashes={}
 def read(name):
  path=root/name
  if not path.is_file():issues.append('missing '+name);return []
  hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest();return rows(path)
 trace=read('trace.jsonl');frames=read('video_frame_map.jsonl')
 if not trace:issues.append('empty original trace')
 if len(trace)!=len(frames):issues.append('trace/video frame count mismatch')
 for i,(t,f) in enumerate(zip(trace,frames)):
  if f.get('video_frame')!=i or f.get('carla_frame')!=t.get('frame') or f.get('time_s')!=t.get('time_s'):issues.append('frame join mismatch at '+str(i))
  if i and t['time_s']<=trace[i-1]['time_s']:issues.append('nonmonotonic original time')
 for c in recording['channels']:
  channel=read('channels/'+c['name']+'.jsonl')
  if len(channel)!=len(trace):issues.append('channel count '+c['name'])
  if any(v.get('value') is None for v in channel):issues.append('unavailable mandatory evidence '+c['name'])
  for t,v in zip(trace,channel):
   if v.get('time_s')!=t.get('time_s'):issues.append('channel time join '+c['name']);break
  rate=c['sampling_rate_hz']
  if any(abs((b['time_s']-a['time_s'])-1/rate)>.0001 for a,b in zip(channel,channel[1:])):issues.append('channel rate '+c['name'])
 for name in ('road.xodr','carla_recorder.log','capture/manifest.json','capture/evidence.jsonl'):
  if not (root/name).is_file():issues.append('missing '+name)
 return dict(passed=not issues,issues=issues,source_sha256=hashes,legal_verdict=None)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output_dir');p.add_argument('--config',default=str(pathlib.Path(__file__).with_name('config.json')));a=p.parse_args();r=validate(a.output_dir,json.loads(pathlib.Path(a.config).read_text())['recording_description']);print(json.dumps(r,indent=2));raise SystemExit(0 if r['passed'] else 2)
