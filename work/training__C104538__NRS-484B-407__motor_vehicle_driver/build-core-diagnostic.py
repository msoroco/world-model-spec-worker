"""Expand a pinned three-frame graph seed into a 480-frame synthetic Core probe.

This uses the frozen Core adapter, decoder and renderer. The repeated graph is
synthetic software evidence and never an original C104538 Native observation.
"""
import hashlib
import json
from pathlib import Path
import pickle
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASE=REPO/'runtime/pipeline/fixtures/retained-speed'
DEST=REPO/'.runtime-work/c104538/core-diagnostic-v2'
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from traffic_spec_adapter.adapter import load_graph

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def lines(path,rows):path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))

def build():
    if DEST.exists():raise ValueError('Retain prior Core diagnostic')
    fixture=DEST/'below_500_ft/positive'
    shutil.copytree(BASE,fixture)
    case=ROOT.name+'__below_500_ft'
    config=json.loads((ROOT/'draft-offline-v10/below_500_ft/primary/config.json').read_text())
    config['synthetic_fixture']=True
    write(fixture/'config.json',config)
    trace0=json.loads((BASE/'trace.jsonl').read_text().splitlines()[0])
    evidence0=json.loads((BASE/'capture/evidence.jsonl').read_text().splitlines()[0])
    native0=json.loads((BASE/'capture/native/frames.jsonl').read_text().splitlines()[0])
    base_graph=load_graph(BASE/'capture/native'/native0['base'])
    traces=[];evidences=[];natives=[]
    for i in range(480):
        frame=1001+i;time=round((i+1)/20,4);simulation=16.273379930108786+time
        trace=json.loads(json.dumps(trace0));trace.update(frame=frame,time_s=time)
        trace['speed_comparison_native'].update(frame=frame,time_s=time)
        trace['environment_measurements'].update(frame=frame,time_s=time)
        trace['speed_comparison_native']['environment_measurements'].update(frame=frame,time_s=time)
        traces.append(trace)
        evidence=json.loads(json.dumps(evidence0));evidence.update(original_frame=frame,
            replay_frame=frame,recording_time_s=time,replay_simulation_time_s=simulation)
        evidence['original_observations'].update(frame=frame,time_s=time)
        evidences.append(evidence)
        native=dict(native0,frame=frame,simulation_time=simulation)
        copied=base_graph.copy();copied.graph['frame']=frame
        copied.graph['simulation_time_s']=simulation
        copied.graph['observed_evidence']=evidence['original_observations']
        name=f'graphs/base/{frame:08d}.pkl'
        with (fixture/'capture/native'/name).open('wb') as output:pickle.dump(copied,output)
        native['base']=name
        natives.append(native)
    lines(fixture/'trace.jsonl',traces)
    lines(fixture/'capture/evidence.jsonl',evidences)
    lines(fixture/'capture/native/frames.jsonl',natives)
    (fixture/'synchronized_motion_records.jsonl').unlink()
    manifest=json.loads((fixture/'capture/manifest.json').read_text())
    manifest.update(case_id=case,frames=480,source_run='synthetic:repeated-pinned-three-frame-graph',
                    synthetic_fixture=True)
    manifest['sources']['trace.jsonl']=sha(fixture/'trace.jsonl')
    write(fixture/'capture/manifest.json',manifest)
    binary=REPO/'.runtime-work/linux_arm64/ffmpeg'
    if not binary.is_file():raise ValueError('Pinned local FFmpeg unavailable')
    video=fixture/'synthetic-480.mkv'
    subprocess.run([str(binary),'-nostdin','-hide_banner','-loglevel','error','-n',
        '-f','lavfi','-i','color=c=black:s=960x540:r=20:d=24',
        '-frames:v','480','-c:v','ffv1',str(video)],check=True,timeout=120)
    video.replace(fixture/'raw.mkv')
    lines(fixture/'video_frames.jsonl',[
        {'video_frame':i,'carla_frame':row['frame'],'time_s':row['time_s']}
        for i,row in enumerate(traces)])
    case_data=next(item for item in json.loads((ROOT/'case-plan.json').read_text())['cases']
                   if item['case_id']==case)
    write(fixture/'case.json',case_data)
    write(fixture/'result.json',{'case_id':case,'video_references':['raw.mkv'],
                               'accepted':False,'provenance_kind':'synthetic'})
    return {'case_id':case,'fixture':str(fixture),'frames':480,
            'trace_sha256':sha(fixture/'trace.jsonl'),
            'evidence_sha256':sha(fixture/'capture/evidence.jsonl'),
            'raw_video_sha256':sha(fixture/'raw.mkv'),
            'graph_seed_sha256':sha(BASE/'capture/native'/native0['base']),
            'synthetic':True}

if __name__=='__main__':print(json.dumps(build()))
