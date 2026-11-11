"""Complete a synthetic Native-shaped capture and exercise pinned Core/render."""
import argparse
import hashlib
import importlib.util
import json
import os
import pickle
import networkx as nx
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',str(ROOT/'.runtime-work/c110454-core-diagnostic-output'))
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
spec=importlib.util.spec_from_file_location('saved_fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from geometry import open_drive
from finalize import finalize
from worker_exchange.runtime_cli import process,render
from worker_exchange.media import audit


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(value,allow_nan=False)+'\n' for value in values))


def enrich(attempt):
    trace=rows(attempt/'trace.jsonl')
    evidence=rows(attempt/'capture/evidence.jsonl')
    samples=rows(attempt/'native_samples.jsonl')
    if len(trace)!=len(evidence) or len(trace)!=len(samples) or len(trace)!=480:
        raise ValueError('Expected 480 joined synthetic samples')
    graph_dir=attempt/'capture/native/graphs/base';graph_dir.mkdir(parents=True)
    frames=[]
    for index,(t,e,n) in enumerate(zip(trace,evidence,samples)):
        frame=t['frame'];time=t['time_s'];x,y=n['native_center_xy_m']
        graph=nx.DiGraph()
        graph.graph.update(frame=frame,simulation_time_s=time,
                           synthetic_diagnostic=True,
                           source='C110454 synthetic saved vehicle rows')
        graph.add_node('ego',sem_class='ego',entity_id=107,
                       vertex=[x,y,.5],forward=[1.0,0.0,0.0],
                       threedbbox=e['ego']['body_vertices_m'])
        (graph_dir/f'{frame:08d}.pkl').write_bytes(pickle.dumps(graph,protocol=4))
        t['position_m']=[x,y,.5]
        t['speed_mph']=t['speed_mps']/.44704
        t['speed_provenance']='synthetic_native_sample'
        t['control']={'throttle':0,'brake':0,'hand_brake':False}
        e.update(replay_frame=frame,replay_simulation_time_s=time,actor_id=107)
        e['ego'].update(position_m=[x,y,.5],heading_deg=t['heading_deg'],
                        speed_mps=t['speed_mps'],
                        speed_provenance='synthetic_native_sample')
        road=1 if x<-7 else 13 if x<7 else 2
        e['world']={'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                    'road_projection':{'road_id':road,'section_id':0,'lane_id':-1,'s_m':x+100}}
        frames.append({'frame':frame,'simulation_time':time,'time_s':time,
                       'base':f'graphs/base/{frame:08d}.pkl',
                       'abstract':f'graphs/abstract/{frame:08d}.pkl',
                       'synthetic_diagnostic':True})
    write_rows(attempt/'trace.jsonl',trace)
    write_rows(attempt/'capture/evidence.jsonl',evidence)
    write_rows(attempt/'capture/native/frames.jsonl',frames)
    (attempt/'road.xodr').write_text(open_drive())
    (attempt/'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    manifest=json.loads((attempt/'capture/manifest.json').read_text())
    manifest.update(sources={'road.xodr':hashlib.sha256((attempt/'road.xodr').read_bytes()).hexdigest(),
                             'trace.jsonl':hashlib.sha256((attempt/'trace.jsonl').read_bytes()).hexdigest()},
                    synthetic_diagnostic=True)
    (attempt/'capture/manifest.json').write_text(json.dumps(manifest))


def make_attempt(path,suffix,full_resolution=False):
    fixture.make_base(path,suffix,480,full_resolution=full_resolution)
    enrich(path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suffix',choices=['reference','contrast'],default='reference')
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c110454-core-'))
    attempt=scratch/'attempt';make_attempt(attempt,args.suffix)
    print('scratch',scratch,flush=True)
    finalize(attempt,attempt/'analysis-report.json')
    core=process(attempt,attempt/'converted',ROOT/'runtime/pipeline/library',
                 ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck')
    config=json.loads((attempt/'config.json').read_text())
    video=render(attempt,attempt/'converted',config['case'])
    decoded=audit(video['video'],480,mapping_sha256=video['frame_map_sha256'],
                  receipt=attempt/'final-decode.json')
    print(json.dumps({'core':core,'render_frames':video['frames'],
                      'final_decode_passed':decoded['passed'],
                      'scope':'synthetic software integration with retained graph templates; no CARLA or acceptance'}))


if __name__=='__main__':main()
