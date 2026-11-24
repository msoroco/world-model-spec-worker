"""Build eight source-hashed branch CPU compatibility recipes."""
import hashlib
import json
from pathlib import Path
from branch_requests import HERE, ASSIGNMENT

ROOT=HERE.parents[1];BASE=HERE/'cases/branch-requests'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj,compact=False):
    path.write_text(json.dumps(obj,separators=(',',':') if compact else None,
                               indent=None if compact else 2,ensure_ascii=False)+'\n')
    if path.stat().st_size>2*1024*1024:raise ValueError('Returned file exceeds 2 MiB: '+str(path))
def jsonl(rows):return ''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows)
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines()]


def build(suffix,candidate):
    bundle=BASE/(suffix if candidate=='primary' else suffix+'-'+candidate);raw=bundle/'raw-fixture'
    construction=bundle/'construction.json';config=json.loads((bundle/'config.json').read_text())
    actors=rows(raw/'native-raw-actors.jsonl');frames=rows(raw/'video_frames.jsonl')
    if len(actors)!=600 or len(frames)!=600:raise ValueError('Short branch diagnostic source')
    generator={'files':{},'graphs':[],'videos':[]};native_frames=[];trace=[];evidence=[];frame_map=[]
    for index,(actor,frame) in enumerate(zip(actors,frames)):
        native=actor['native_frame'];time=actor['time_s'];ego=actor['ego']
        if actor['frame']!=index or frame['native_frame']!=native or frame['video_frame']!=index:
            raise ValueError('Branch actor/video join differs')
        graph_ref=f'graphs/base/{native:08d}.adapter.json';center=ego['center_native_xyz_m']
        native_frames.append({'frame':native,'time_s':time,'simulation_time':time,
                              'adapter_graph':graph_ref,'synthetic_diagnostic':True})
        trace.append({'frame':native,'time_s':time,'position':{'x':center[0],'y':center[1],'z':center[2]},
                      'position_m':center,'speed_mph':ego['speed_mps']/.44704,'heading_deg':0,
                      'speed_mps':ego['speed_mps'],'control':{},'velocity_mps':ego['velocity_native_xyz_mps'],
                      'synthetic_diagnostic':True})
        frame_map.append({'video_frame':index,'native_frame':native,'carla_frame':native,
                          'time_s':time,'synthetic_diagnostic':True})
        evidence.append({'original_frame':native,'replay_frame':native,'actor_id':ego['actor_id'],
                         'recording_time_s':time,'replay_simulation_time_s':time,
                         'ego':{'position_m':center,'speed_mps':ego['speed_mps'],
                                'speed_provenance':'synthetic_native_sample','heading_deg':0,
                                'body_vertices_m':ego['body_native_xyz_m']},
                         'world':{'weather':{'sun_altitude_angle':90,'precipitation':0,'wetness':0}},
                         'synthetic_diagnostic':True})
        nodes=[{'id':'ego','attributes':{'sem_class':'ego','entity_id':ego['actor_id'],
                'vertex':center,'forward':[1,0,0],'threedbbox':ego['body_native_xyz_m'],
                'carla_speed':ego['speed_mps']}}]
        officer=actor.get('officer_actor')
        if officer is not None:
            nodes.append({'id':'requested_officer','attributes':{'sem_class':'pedestrian',
                'entity_id':officer['actor_id'],'vertex':officer['center_native_xyz_m'],
                'forward':[0,1,0],'threedbbox':officer['body_native_xyz_m'],'carla_speed':0}})
        generator['graphs'].append({'path':'capture/native/'+graph_ref,
            'attributes':{'frame':native,'time_s':time,'synthetic_diagnostic':True,
                          'source':'C10389 branch authored request fixture'},'nodes':nodes,'edges':[]})
    for name,data in [('capture/native/frames.jsonl',native_frames),('trace.jsonl',trace),
                      ('video_frames.jsonl',frame_map),('capture/evidence.jsonl',evidence)]:
        generator['files'][name]=jsonl(data)
    generator['files']['capture/manifest.json']=json.dumps({'source_kind':'synthetic_diagnostic',
        'frames':600,'rate_hz':20,'extraction_confirmed':True,'original_native_observed':False,
        'sources':{'road.xodr':sha(bundle/'alley-stop.xodr'),
                   'trace.jsonl':hashlib.sha256(generator['files']['trace.jsonl'].encode()).hexdigest()}})+'\n'
    generator['files']['capture/recorder_info.txt']='Create 101: vehicle.tesla.model3\n'
    generator['videos']=[{'path':name+'.mkv','frames':600,'width':1920 if name=='overview' else 1280,
                          'height':1080 if name=='overview' else 720,'fps':20,'color':'black'}
                         for name in ('overview','approach','reference_corner','driver_reference','forward')]
    write(bundle/'generator.json',generator,compact=True)
    source_names=('native-map-readback.json','native-raw-actors.jsonl','frame-review.jsonl','native-capture-report.json')
    sources=[{'path':name,'source':(raw/name).relative_to(ROOT).as_posix(),
              'sha256':sha(raw/name)} for name in source_names]
    sources.append({'path':'road.xodr','source':(bundle/'alley-stop.xodr').relative_to(ROOT).as_posix(),
                    'sha256':sha(bundle/'alley-stop.xodr')})
    write(bundle/'recipe.json',{'format':'worker-fixture-recipe','sources':sources,
          'generator':{'source':(bundle/'generator.json').relative_to(ROOT).as_posix(),
                       'sha256':sha(bundle/'generator.json')}})
    index=1 if suffix.startswith('signal_') else 2
    write(bundle/'measurement-contract.json',{'format':'worker-measurement-contract',
          'case_id':config['case_id'],'requirements':[{'disposition_index':index,
              'requirement':'NRS-484B-300-1','source':'NRS 484B.300(1)',
              'output_key':'branch_response','method':'measure_branch_response',
              'value_type':'object','kind':'measured',
              'inputs':['native-raw-actors.jsonl','native-map-readback.json']}],
          'negative':{'remove':['native-raw-actors.jsonl'],
              'error_contains':'Missing required source: native-raw-actors.jsonl'},
          'status':'unselected_diagnostic'})
    write(bundle/'probe-manifest.json',{'format':'worker-unselected-current-v2-probe-manifest',
          'assignment_id':ASSIGNMENT,'runtime_manifest_sha256':sha(ROOT/'runtime/SOURCE-MANIFEST.json'),
          'status':'draft_not_selected','cases':[{'case_id':config['case_id'],
              'kind':'draft_not_selected','id':candidate,
              'construction':construction.relative_to(HERE).as_posix(),
              'construction_sha256':sha(construction),'candidate_risk':{'status':'physical',
                  'reason':'Original signal/officer source visibility and response require review'},
              'candidates':[],'measurement_contract':(bundle/'measurement-contract.json').relative_to(HERE).as_posix(),
              'measurement_procedure':{'entrypoint':'finalize.py','status':'saved_source_diagnostic'},
              'fixture_recipe':(bundle/'recipe.json').relative_to(ROOT).as_posix()}]})
    return {'case_id':config['case_id'],'candidate':candidate,
            'generator_bytes':(bundle/'generator.json').stat().st_size,
            'manifest_sha256':sha(bundle/'probe-manifest.json')}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--suffix',required=True);parser.add_argument('--candidate',required=True)
    a=parser.parse_args();print(json.dumps(build(a.suffix,a.candidate),sort_keys=True))
