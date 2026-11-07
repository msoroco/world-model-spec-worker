"""Complete a synthetic Native-shaped capture and exercise pinned Core/render."""
import argparse
import hashlib
import importlib.util
import json
import pickle
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
spec=importlib.util.spec_from_file_location('saved_fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from geometry import open_drive
from finalize import finalize
from finalize_numeric import finalize as finalize_numeric
from finalize_exception import finalize as finalize_exception
from traffic_spec_adapter.adapter import load_graph
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
    graph=load_graph(ROOT/'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl')
    graph_dir=attempt/'capture/native/graphs/base';graph_dir.mkdir(parents=True)
    frames=[]
    for index,(t,e,n) in enumerate(zip(trace,evidence,samples)):
        frame=t['frame'];time=t['time_s'];x,y=n['native_center_xy_m']
        graph.graph['frame']=frame
        (graph_dir/f'{frame:08d}.pkl').write_bytes(pickle.dumps(graph,protocol=4))
        t['position_m']=[x,y,.5]
        t['speed_mph']=t['speed_mps']/.44704
        t['control']={'throttle':0,'brake':0,'hand_brake':False}
        e.update(replay_frame=frame,replay_simulation_time_s=time,actor_id=107)
        e['ego'].update(position_m=[x,y,.5],heading_deg=t['heading_deg'],
                        speed_mps=t['speed_mps'],
                        speed_provenance='original_trace_actor_get_velocity')
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
    if suffix in ('exception_2_2','exception_3_2'):
        road=(HERE/'native/road_exception_device.xodr').read_text()
        (path/'road.xodr').write_text(road)
        meta_path=path/'capture/manifest.json';meta=json.loads(meta_path.read_text())
        meta['sources']['road.xodr']=hashlib.sha256(road.encode()).hexdigest()
        meta_path.write_text(json.dumps(meta))
    if suffix.startswith('exception_'):
        from exception_case import BRANCHES
        branch,polarity=BRANCHES[suffix]
        frames=[r['native_frame'] for r in rows(path/'video_frames.jsonl')]
        packet={'source_kind':'native_context_schema','branch':branch,
                'requested_polarity':polarity,'original_frames':frames,
                'observed_exception_source_ids':[],'synthetic_diagnostic':True,
                'physical_observation_claimed':False}
        if polarity=='present':
            packet['observed_exception_source_ids']=['synthetic-source']
            if branch=='necessary_traffic_conflict':
                write_rows(path/'other_actor_history.jsonl',[{'native_frame':frame,'conflict_occupancy':frame==320,'synthetic_diagnostic':True} for frame in frames])
                write_rows(path/'ego_response_history.jsonl',[{'native_frame':frame,
                    'brake_applied':index==221,'speed_mps':4.0 if index<221 else 3.0,
                    'synthetic_diagnostic':True} for index,frame in enumerate(frames)])
                packet.update(other_actor_frames=[220,221],ego_brake_frames=[221],
                    intersection_boundary_source='native_map_readback')
            elif branch=='compliance_with_law':
                laws=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())
                law=laws['laws']['NRS-484B-300-1']['law']['text']
                packet.update(cited_law_id='NRS-484B-300-1',
                    cited_law_text_sha256=hashlib.sha256(law.encode()).hexdigest(),
                    ego_action_frames=[221])
            else:
                packet.update(original_pixel_sha256=hashlib.sha256((path/'parking.mkv').read_bytes()).hexdigest(),
                    direction_source_id='synthetic-device',direction_frame=221,
                    ego_action_frames=[221])
        (path/'exception_context.json').write_text(json.dumps(packet,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suffix',choices=['witness_1','witness_2','numeric_1_0','numeric_1_1','numeric_1_2','exception_1_1','exception_1_2','exception_2_1','exception_2_2','exception_3_1','exception_3_2'],default='witness_1')
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c110454-lvmc-core-'))
    attempt=scratch/'attempt';make_attempt(attempt,args.suffix)
    print('scratch',scratch,flush=True)
    (finalize_exception if args.suffix.startswith('exception_') else finalize_numeric if args.suffix.startswith('numeric_') else finalize)(attempt,attempt/'analysis-report.json')
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
