"""Build a full-profile synthetic source packet and invoke pinned saved processing."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import importlib.util
import argparse

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c110454-current-profile'
CASE=HERE.name+'__witness_1'
MANIFEST=HERE/'draft-current-primary-manifest.json'
SOURCE=SCRATCH/'saved-source-v4-witness_1'
ATTEMPT=SCRATCH/'saved-attempt-v4-witness_1'
OUTPUT=SCRATCH/'processed-v4-witness_1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def enrich_current_graph_sources(source):
    """Reconstruct a synthetic JSON graph frame index for current Core input."""
    trace=[json.loads(x) for x in (source/'trace.jsonl').read_text().splitlines()]
    evidence=[json.loads(x) for x in (source/'capture/evidence.jsonl').read_text().splitlines()]
    samples=[json.loads(x) for x in (source/'native_samples.jsonl').read_text().splitlines()]
    if not len(trace)==len(evidence)==len(samples)==600:raise ValueError('600 source samples required')
    graph_dir=source/'capture/native/graphs';graph_dir.mkdir(parents=True)
    frames=[]
    for t,e,n in zip(trace,evidence,samples):
        frame=t['frame'];time=t['time_s'];x,y=n['native_center_xy_m']
        t['position_m']=[x,y,.5];t['speed_mph']=t['speed_mps']/.44704
        t['control']={'throttle':0,'brake':0,'hand_brake':False}
        e.update(replay_frame=frame,replay_simulation_time_s=time,actor_id=107)
        e['ego'].update(position_m=[x,y,.5],heading_deg=t['heading_deg'],
                        speed_mps=t['speed_mps'],speed_provenance='synthetic_native_sample')
        road=1 if x<-7 else 13 if x<7 else 2
        e['world']={'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                    'road_projection':{'road_id':road,'section_id':0,'lane_id':-1,'s_m':x+100}}
        relative=f'graphs/{frame:08d}.json'
        graph={'format':'native-adapter-graph-v1','multigraph':False,
               'metadata':{'frame':frame,'simulation_time_s':time},'nodes':[],'edges':[]}
        (graph_dir/f'{frame:08d}.json').write_text(json.dumps(graph)+'\n')
        frames.append({'frame':frame,'simulation_time':time,'time_s':time,
                       'adapter_graph':relative,'synthetic_diagnostic':True})
    (source/'trace.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in trace))
    (source/'capture/evidence.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in evidence))
    frame_path=source/'capture/native/frames.jsonl';frame_path.write_text(''.join(json.dumps(x)+'\n' for x in frames))
    road=(HERE/'native/road.xodr').read_bytes();(source/'road.xodr').write_bytes(road)
    (source/'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    meta_path=source/'capture/manifest.json';meta=json.loads(meta_path.read_text())
    meta.update(sources={'road.xodr':sha(source/'road.xodr'),'trace.jsonl':sha(source/'trace.jsonl')},
                synthetic_diagnostic=True)
    meta_path.write_text(json.dumps(meta)+'\n')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suffix',default='v5')
    parser.add_argument('--validator',type=Path,default=ROOT/'.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck')
    args=parser.parse_args()
    source=SCRATCH/('saved-source-'+args.suffix+'-witness_1')
    attempt=SCRATCH/('saved-attempt-'+args.suffix+'-witness_1')
    output=SCRATCH/('processed-'+args.suffix+'-witness_1')
    sys.path.insert(0,str(HERE))
    spec=importlib.util.spec_from_file_location('saved_fixture',HERE/'saved-fixture-proof.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.make_base(source,'witness_1',600,full_resolution=True)
    enrich_current_graph_sources(source)
    for old,new in (('intersection','reference_corner'),('parking','driver_reference')):
        (source/(old+'.mkv')).rename(source/(new+'.mkv'))
    selected=json.loads((HERE/'draft-current-primaries/witness_1/construction.json').read_text())
    cfg=json.loads(next(f['content'] for f in selected['files'] if f['path']=='config.json'))
    (source/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    shutil.copytree(SCRATCH/'offline-v2-witness_1',attempt)
    for p in source.rglob('*'):
        if p.is_file():
            q=attempt/p.relative_to(source);q.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,q)
    selection=json.loads((attempt/'candidate-selection.json').read_text())
    selection['manifest_sha256']=sha(MANIFEST)
    selection['construction_sha256']=sha(HERE/'draft-current-primaries/witness_1/construction.json')
    (attempt/'candidate-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    env=dict(os.environ)
    cmd=[sys.executable,str(ROOT/'runtime.py'),'process-saved','--manifest',str(MANIFEST),
         '--case',CASE,'--attempt',str(attempt),'--output',str(output),
         '--library',str(ROOT/'runtime/pipeline/library'),
         '--validator',str(args.validator)]
    proc=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
    versions=sorted(output.glob('v*'))
    feedback=versions[-1]/'feedback.json' if versions else None
    return {'command':cmd,'exit_code':proc.returncode,'stdout_tail':proc.stdout[-2000:],
            'feedback':json.loads(feedback.read_text()) if feedback and feedback.exists() else None,
            'original_sources_preserved':all(sha(p)==sha(attempt/p.relative_to(source)) for p in source.rglob('*') if p.is_file()),
            'synthetic_diagnostic':True,'native_executed':False}
if __name__=='__main__':print(json.dumps(main(),indent=2))
