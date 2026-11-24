"""Build source-hashed selected crossroads candidates from exact Native requests."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = None
SOURCE = None
BUNDLE = None
PREFIX = None
SUFFIX = None
CANDIDATE = None


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def rows(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(item, sort_keys=True) + '\n' for item in records))


def main(suffix, candidate):
    global CASE, SOURCE, BUNDLE, PREFIX, SUFFIX, CANDIDATE
    SUFFIX, CANDIDATE = suffix, candidate
    CASE = HERE.name + '__' + suffix
    PREFIX = f'selected-v3/{suffix}/{candidate}'
    SOURCE = HERE / PREFIX / 'sources'
    BUNDLE = HERE / 'native/drafts' / suffix / candidate
    base = json.loads((HERE / 'native/runtime-drafts' / suffix / candidate / 'construction.json').read_text())
    config = json.loads((BUNDLE / 'config.json').read_text())
    config.update(cell_id='C111294', actor='motor_vehicle_driver', law_id='NRS-484B-250-2',
                  candidate_id=candidate, required_atoms=[], source_packets=[],
                  selected_case_id=CASE, rate_hz=20, duration_s=30,
                  cameras=[{'name': n, 'fps': 20, 'width': 1920 if n == 'overview' else 1280,
                            'height': 1080 if n == 'overview' else 720,
                            'pose_strategy': 'fixed_overview' if n == 'overview' else 'fixed_approach',
                            'fov_deg': 80} for n in
                           ('overview', 'approach', 'reference_corner', 'driver_reference')],
                  case={'case_id': CASE}, supported_case_ids=[CASE],
                  status='selected_cpu_prepared_original_unverified')
    recording = {'channels': [
        {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': 'Retained actor body rows', 'time_window': '30 s / 600 frames',
         'reference_frame': 'original frame/time and authored road',
         'uncertainty': '50 ms frame bracket; physical and legal review pending'}
        for name in ('ego_body', 'other_body')], 'context_inputs': [],
        'limitations': ['Synthetic CPU source; official device governance and legal precedence unverified']}
    base['recording_description'] = recording
    base['files'] = [item for item in base['files'] if item['path'] != 'config.json']
    base['files'].append({'path': 'config.json', 'content': json.dumps(config, indent=2, sort_keys=True) + '\n'})
    base['files'].append({'path': 'finalize.py', 'content':
        (HERE / ('native/finalize_v2.py' if suffix == 'controlled_1' else
                 'native/finalize_v2_contrast.py')).read_text()})
    base['status'] = 'selected_cpu_prepared_original_unverified'
    construction = HERE / PREFIX / 'construction.json'
    write(construction, base)

    SOURCE.mkdir(parents=True, exist_ok=True)
    (SOURCE / 'road.xodr').write_bytes((BUNDLE / 'crossroads.xodr').read_bytes())
    raw = json.loads((HERE / 'native/synthetic' / suffix / candidate / 'raw.json').read_text())
    write(SOURCE / 'actor-history.json', raw)
    write(SOURCE / 'road-context.json', {'source_kind': 'synthetic_cpu_diagnostic',
          'ego_highway_roads': [250,251,252], 'other_highway_roads': [253,254,255],
          'ego_entry_boundary_x_m': -20, 'other_entry_boundary_y_m': -20,
          'official_device_governance_verified': False,
          'opposite_direction_left_turn_exclusion_resolved': False,
          'subsection_4_exception_resolved': False})
    trace, frame_map, evidence, graphs, native_frames = [], [], [], [], []
    for row in raw['rows']:
        frame = row['frame']; time = row['time_s']
        ego = row['ego']; other = row['other']
        x,y,z = ego['center_xyz_m']
        adjacent = raw['rows'][frame+1]['ego']['center_xyz_m'] if frame < 599 else \
            raw['rows'][frame-1]['ego']['center_xyz_m']
        sign = 1 if frame < 599 else -1
        measured_velocity = [sign * (adjacent[j] - ego['center_xyz_m'][j]) * 20
                             for j in range(3)]
        trace.append({'frame': frame, 'time_s': time, 'position': {'x':x,'y':y,'z':z},
                      'position_m': [x,y,z], 'heading_deg': 0,
                      'velocity_mps': measured_velocity,
                      'speed_mps': ego['speed_mps'], 'speed_mph': ego['speed_mps']*2.2369362920544,
                      'control': {'throttle':0,'brake':0,'hand_brake':False}})
        frame_map.append({'carla_frame':frame,'native_frame':frame,'time_s':time,'video_frame':frame})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'ego': {'body_vertices_m': ego['body_xyz_m'], 'position_m':[x,y,z],
                                 'heading_deg':0,'speed_mps':ego['speed_mps'],
                                 'speed_provenance':'synthetic_native_sample',
                                 'synthetic_diagnostic':True},
                         'other_actors':[{'actor_id':11,'body_vertices_m':other['body_xyz_m'],
                                          'position_m':other['center_xyz_m']}],
                         'replay_frame':frame,'replay_simulation_time_s':time,'actor_id':10,
                         'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':250,'section_id':0,'lane_id':-1,'s_m':x+100}}})
        relative = f'graphs/base/{frame:08d}.adapter.json'
        native_frames.append({'frame':frame,'simulation_time':time,'adapter_graph':relative,
                              'base':relative,'nodes':2,'edges':0})
        graphs.append({'path':'capture/native/'+relative,
                       'attributes':{'frame':frame,'simulation_time_s':time,'synthetic_diagnostic':True,
                                     'source':'C111294 crossroads synthetic actor diagnostic'},
                       'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':10,
                                 'vertex':[x,y,z],'forward':[1.0,0.0,0.0],
                                 'threedbbox':ego['body_xyz_m']}},
                                {'id':'other','attributes':{'sem_class':'vehicle','entity_id':11,
                                  'vertex':other['center_xyz_m'],'forward':[0.0,1.0,0.0],
                                  'threedbbox':other['body_xyz_m']}}], 'edges':[]})
    rows(SOURCE/'trace.jsonl',trace)
    rows(SOURCE/'video_frames.jsonl',frame_map)
    rows(SOURCE/'capture/evidence.jsonl',evidence)
    write(SOURCE/'capture/manifest.json',{'extraction_confirmed':True,'frames':600,
          'synthetic_diagnostic':True,'sources':{'road.xodr':sha(SOURCE/'road.xodr'),
                                               'trace.jsonl':sha(SOURCE/'trace.jsonl')}})
    spec={'files':{'capture/native/frames.jsonl':''.join(json.dumps(r,separators=(',',':'))+'\n' for r in native_frames),
                   'capture/recorder_info.txt':'synthetic CPU diagnostic; no CARLA recorder\nCreate 10: vehicle.tesla.model3 (0)\nCreate 11: vehicle.audi.a2 (0)\n'},
          'graphs':graphs,
          'videos':[{'path':n+'.mkv','frames':600,'width':1920 if n=='overview' else 1280,
                     'height':1080 if n=='overview' else 720,'fps':20,'color':'black'} for n in
                    ('overview','approach','reference_corner','driver_reference')]}
    spec_path=HERE/PREFIX/'fixture-spec.json';write(spec_path,spec)
    sources=[{'path':str(p.relative_to(SOURCE)),'source':str(p.relative_to(REPO)),
              'sha256':sha(p)} for p in sorted(SOURCE.rglob('*')) if p.is_file()]
    recipe=HERE/PREFIX/'fixture-recipe.json'
    write(recipe,{'format':'worker-fixture-recipe','sources':sources,
                  'generator':{'source':str(spec_path.relative_to(REPO)),'sha256':sha(spec_path)}})
    contract=HERE/PREFIX/'measurement-contract.json'
    write(contract,{'format':'worker-measurement-contract','case_id':CASE,
                    'requirements':[{'disposition_index':0,'requirement':'NRS-484B-250-2',
                                     'source':'NRS 484B.250(2); with 484B.250(5)',
                                     'output_key':'crossroads_entry_measurement',
                                     'method':'measure_entry','value_type':'object','kind':'measured',
                                     'inputs':['actor-history.json','road-context.json',
                                               'video_frames.jsonl','trace.jsonl','capture/evidence.jsonl']}],
                    'negative':{'remove':['actor-history.json'],
                                'error_contains':'Missing required source: actor-history.json'},
                    'status':'selected_cpu_prepared_original_unverified'})
    runtime=json.loads((REPO/'batch.json').read_text())
    manifest=HERE/PREFIX/'diagnostic-manifest.json'
    write(manifest,{'format':'worker-unselected-draft-construction-manifest-v1',
                    'assignment_id':HERE.name,'status':'draft_not_selected',
                    'runtime_manifest_sha256':runtime['runtime']['source_manifest_sha256'],
                    'cases':[{'case_id':CASE,'kind':'delivery','id':candidate,
                              'construction':'construction.json','construction_sha256':sha(construction),
                              'fixture_recipe':str(recipe.relative_to(REPO)),
                              'measurement_contract':'measurement-contract.json',
                              'measurement_procedure':{'entrypoint':'finalize.py'},
                              'recording_description':recording,'candidates':[],
                              'candidate_risk':{'status':'physical','reason':'Original two-highway entry and legal applicability need review'}}]})
    print(json.dumps({'manifest_sha256':sha(manifest),'recipe_sha256':sha(recipe),
                      'spec_sha256':sha(spec_path),'construction_sha256':sha(construction)}))

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('controlled_1','controlled_2'), required=True)
    parser.add_argument('--candidate', choices=('primary','fallback1','fallback2'), required=True)
    args = parser.parse_args()
    main(args.suffix, args.candidate)
