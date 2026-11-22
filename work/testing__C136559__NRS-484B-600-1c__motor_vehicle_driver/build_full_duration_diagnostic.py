"""Extend an explicitly synthetic nine-frame diagnostic; never Native evidence."""
import copy, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
src=Path(sys.argv[1]);dst=Path(sys.argv[2]);count=600
if dst.exists(): raise SystemExit('destination exists')
shutil.copytree(src,dst,copy_function=os.link)
def write(path,content):
    path.unlink();path.write_text(content)
def rows(name):return [json.loads(x) for x in (dst/name).read_text().splitlines() if x]
def dump(name,data):write(dst/name,''.join(json.dumps(x,separators=(',',':'),allow_nan=False)+'\n' for x in data))
def shift_body(points,dx):return [[x+dx,*p[1:]] for p in points for x in [p[0]]]
def shift_participant(p,dx,x):
    if p.get('actor_id')==205:
        p['position_m'][0]=x;p['speed_mps']=speed
        if 'body_vertices_m' in p:p['body_vertices_m']=shift_body(p['body_vertices_m'],dx)
streams={n:rows(n) for n in ('subject_motion.jsonl','trace.jsonl','speed_samples.jsonl','body_history.jsonl','capture/evidence.jsonl','video_frames.jsonl','capture/native/frames.jsonl')}
assert {len(x) for x in streams.values()}=={9}
seed_rows={n:copy.deepcopy(value[-1]) for n,value in streams.items()}
first=streams['trace.jsonl'][0];last=streams['trace.jsonl'][-1];speed=last['speed_mps'];t0=first['time_s'];x0=first['position_m'][0]
simulation_t0=streams['capture/native/frames.jsonl'][0]['simulation_time']
last_x=last['position_m'][0]
for i in range(9,count):
    frame=38033+i;t=round(t0+i/20,8);simulation_t=round(simulation_t0+i/20,8);x=x0+speed*(t-t0);dx=x-last_x
    for name,old in streams.items():
        row=copy.deepcopy(seed_rows[name])
        for k in ('frame','original_frame','replay_frame','carla_frame','native_frame'):
            if k in row:row[k]=frame
        for k in ('time_s','recording_time_s','replay_simulation_time_s','simulation_time'):
            if k in row:row[k]=simulation_t if k in ('replay_simulation_time_s','simulation_time') else t
        if name in ('trace.jsonl','speed_samples.jsonl'):
            row['position_m'][0]=x;row['position']['x']=x
        if name=='subject_motion.jsonl':row['road_s_m']=x
        if name=='body_history.jsonl':row['vertices_m']=shift_body(row['vertices_m'],dx)
        if name=='capture/evidence.jsonl':
            row['ego']['position_m'][0]=x;row['ego']['body_vertices_m']=shift_body(row['ego']['body_vertices_m'],dx)
            row['world']['road_projection']['s_m']=x
            obs=row['original_observations'];obs['frame']=frame;obs['time_s']=t
            for p in obs['participants']:shift_participant(p,dx,x)
            for s in obs['rgb_sensors']:
                if s.get('parent_actor_id')==205:s['position_m'][0]+=dx
        if name=='video_frames.jsonl':row['video_frame']=i
        if name=='capture/native/frames.jsonl':
            for k in ('abstract','base','adapter_graph'):
                row[k]=str(Path(row[k]).with_name(f'{frame:08d}.adapter.json'))
        old.append(row)
for n,x in streams.items():dump(n,x)
for kind in ('base','abstract'):
    base=dst/f'capture/native/graphs/{kind}/00038041.adapter.json';seed=json.loads(base.read_text())
    for i in range(9,count):
        frame=38033+i;t=round(t0+i/20,8);simulation_t=round(simulation_t0+i/20,8);x=x0+speed*(t-t0);dx=x-last_x
        d=copy.deepcopy(seed);meta=d['metadata'];meta['frame']=frame;meta['simulation_time_s']=simulation_t
        if kind=='base':
            obs=meta['observed_evidence'];obs['frame']=frame;obs['time_s']=t
            for p in obs.get('participants',[]):shift_participant(p,dx,x)
            for s in obs.get('rgb_sensors',[]):
                if s.get('parent_actor_id')==205:s['position_m'][0]+=dx
        (base.parent/f'{frame:08d}.adapter.json').write_text(json.dumps(d,separators=(',',':'))+'\n')
    print('graphs',kind,count,flush=True)
for n in ('overview','approach','reference_corner','driver_reference'):
    out=dst/(n+'.mkv');out.unlink()
    cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-stream_loop','-1','-i',str(src/(n+'.mkv')),'-frames:v',str(count),'-c:v','copy',str(out)]
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode:raise RuntimeError(n+': '+r.stderr)
    print('video',n,out.stat().st_size,flush=True)
provenance=json.loads((dst/'fixture-provenance.json').read_text());provenance['frames']=count
write(dst/'fixture-provenance.json',json.dumps(provenance,separators=(',',':'))+'\n')
manifest=json.loads((dst/'capture/manifest.json').read_text());manifest['frames']=count;manifest['source_run']='fixture:600-synthetic-original-frame-extension'
for n in manifest['sources']:
    f=dst/n
    if f.exists():manifest['sources'][n]=hashlib.sha256(f.read_bytes()).hexdigest()
write(dst/'capture/manifest.json',json.dumps(manifest,separators=(',',':'))+'\n')
result=json.loads((dst/'result.json').read_text())
for n in result.get('source_hashes',{}):
    f=dst/n
    if f.exists():result['source_hashes'][n]=hashlib.sha256(f.read_bytes()).hexdigest()
result['capture_evidence_sha256']=hashlib.sha256((dst/'capture/evidence.jsonl').read_bytes()).hexdigest()
write(dst/'result.json',json.dumps(result,indent=2)+'\n')
print('extended',count,flush=True)
