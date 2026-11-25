"""Build exact 600-frame current-v2 signal-outage CPU diagnostic."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
CASE=HERE.name+'__controlled_2'
SOURCE=HERE/'selected-v3-contrast-sources'
SOURCE_REQUEST=HERE/'selected-contrast-request.jsonl'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def rows(path,records):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in records))

def main():
    base=json.loads((HERE/'selected-offline/controlled_2/primary/construction.json').read_text())
    config=json.loads(next(x['content'] for x in base['files'] if x['path']=='config.json'))
    config.update(case_id=CASE,cell_id='C111331',actor='motor_vehicle_driver',law_id='NRS-484B-250-4',
                  candidate_id='primary',required_atoms=[],source_packets=[],
                  cameras=[{'name':n,'fps':20} for n in ('overview','approach','reference_corner','driver_reference')],
                  case={'case_id':CASE},supported_case_ids=[CASE],status='unselected_cpu_diagnostic')
    recording={'channels':[{'name':n,'unit':'structured','sampling_rate_hz':20,
                'method':'Retained original-frame synthetic source row',
                'time_window':'30 s / 600 frames','reference_frame':'original frame/time',
                'uncertainty':'50 ms frame bracket; physical and legal review pending'}
                for n in ('ego_front','signal_request')],
               'context_inputs':[],
               'limitations':['Synthetic request only; original vehicular signal state and actual stop unverified']}
    base['recording_description']=recording
    base['files']=[x for x in base['files'] if x['path']!='config.json']
    base['files'].append({'path':'config.json','content':json.dumps(config,indent=2,sort_keys=True)+'\n'})
    base['files'].append({'path':'finalize.py','content':(HERE/'native/selected_v3_finalize_contrast.py').read_text()})
    base['status']='unselected_cpu_diagnostic'
    construction=HERE/'selected-v3-contrast-construction.json';write(construction,base)
    SOURCE.mkdir(parents=True,exist_ok=True)
    road=HERE/'selected-road.xodr'
    (SOURCE/'road.xodr').write_bytes(road.read_bytes())
    request=[json.loads(x) for x in SOURCE_REQUEST.read_text().splitlines()]
    rows(SOURCE/'vehicle-history.jsonl',request)
    write(SOURCE/'signal-context.json',{'source_kind':'synthetic_cpu_diagnostic',
          'signal_id':'c111331-installed-uncovered-vehicular-head',
          'official_signal_state_verified':False,'marked_stop_line_x_m':-26,
          'near_side_crosswalk_x_m':-23,'intersection_entry_x_m':-20,
          'physical_stop_verified':False,'yielding_verified':False})
    trace,frame_map,evidence,graphs,native_frames=[],[],[],[],[]
    for row in request:
        frame=row['frame'];time=row['time_s'];x,y=row['ego_center_xy_m'];ox,oy=row['other_center_xy_m']
        body=[[x+dx,y+dy,z] for dx in (-2,2) for dy in (-.9,.9) for z in (0,1.5)]
        other=[[ox+dy,oy+dx,z] for dx in (-2,2) for dy in (-.9,.9) for z in (0,1.5)]
        speed=0 if frame>0 and row['ego_center_xy_m']==request[frame-1]['ego_center_xy_m'] else 4.0
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
                      'position_m':[x,y,.5],'heading_deg':0,'speed_mps':speed,
                      'speed_mph':speed*2.2369362920544,
                      'control':{'throttle':0,'brake':0,'hand_brake':False}})
        frame_map.append({'carla_frame':frame,'native_frame':frame,'time_s':time,'video_frame':frame})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'ego':{'body_vertices_m':body,'position_m':[x,y,.5],
                                'heading_deg':0,'speed_mps':speed,
                                'speed_provenance':'synthetic_native_sample','synthetic_diagnostic':True},
                         'other_actors':[{'actor_id':11,'body_vertices_m':other,
                                          'position_m':[ox,oy,.5]}],
                         'replay_frame':frame,'replay_simulation_time_s':time,'actor_id':10,
                         'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':250,'section_id':0,'lane_id':-1,'s_m':x+100}}})
        relative=f'graphs/base/{frame:08d}.adapter.json'
        native_frames.append({'frame':frame,'simulation_time':time,'adapter_graph':relative,
                              'base':relative,'nodes':2,'edges':0})
        graphs.append({'path':'capture/native/'+relative,
                       'attributes':{'frame':frame,'simulation_time_s':time,'synthetic_diagnostic':True,
                                     'source':'C111331 inoperative-signal request diagnostic'},
                       'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':10,
                                 'vertex':[x,y,.5],'forward':[1,0,0],'threedbbox':body}},
                                {'id':'other','attributes':{'sem_class':'vehicle','entity_id':11,
                                  'vertex':[ox,oy,.5],'forward':[0,1,0],'threedbbox':other}}],
                       'edges':[]})
    rows(SOURCE/'trace.jsonl',trace);rows(SOURCE/'video_frames.jsonl',frame_map)
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
    spec_path=HERE/'selected-v3-contrast-fixture-spec.json';write(spec_path,spec)
    sources=[{'path':str(p.relative_to(SOURCE)),'source':str(p.relative_to(REPO)),
              'sha256':sha(p)} for p in sorted(SOURCE.rglob('*')) if p.is_file()]
    recipe=HERE/'selected-v3-contrast-fixture-recipe.json'
    write(recipe,{'format':'worker-fixture-recipe','sources':sources,
                  'generator':{'source':str(spec_path.relative_to(REPO)),'sha256':sha(spec_path)}})
    contract=HERE/'selected-v3-contrast-measurement-contract.json'
    write(contract,{'format':'worker-measurement-contract','case_id':CASE,
                    'requirements':[{'disposition_index':0,'requirement':'NRS-484B-250-4',
                      'source':'NRS 484B.250(4)','output_key':'inoperative_signal_stop_measurement',
                      'method':'measure_stop','value_type':'object','kind':'measured',
                      'inputs':['vehicle-history.jsonl','signal-context.json','video_frames.jsonl',
                                'trace.jsonl','capture/evidence.jsonl']}],
                    'negative':{'remove':['vehicle-history.jsonl'],
                                'error_contains':'Missing required source: vehicle-history.jsonl'},
                    'status':'unselected_contract_draft'})
    runtime=json.loads((REPO/'batch.json').read_text())
    manifest=HERE/'selected-v3-contrast-manifest.json'
    write(manifest,{'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':HERE.name,'status':'draft_not_selected',
        'runtime_manifest_sha256':runtime['runtime']['source_manifest_sha256'],
        'cases':[{'case_id':CASE,'kind':'draft_not_selected','id':'primary',
                  'construction':construction.name,'construction_sha256':sha(construction),
                  'fixture_recipe':str(recipe.relative_to(REPO)),
                  'measurement_contract':contract.name,
                  'measurement_procedure':{'entrypoint':'finalize.py'},
                  'recording_description':recording,'candidates':[],
                  'candidate_risk':{'status':'physical','reason':'Original signal outage and stop need Native readback'}}]})
    print(json.dumps({'manifest_sha256':sha(manifest),'recipe_sha256':sha(recipe),'construction_sha256':sha(construction)}))

if __name__=='__main__':main()
