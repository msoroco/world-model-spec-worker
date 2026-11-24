"""Build exact 600-frame current-v2 flashing-arrow CPU diagnostic."""
import hashlib
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from request import road, rows, check
CASE=HERE.name+'__controlled_1'
SOURCE=HERE/'current-v2-primary-sources'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def write_rows(path,records):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in records))

def main():
    check('yield_then_turn')
    base=json.loads((HERE/'draft-yield_then_turn-construction.json').read_text())
    config=json.loads(next(x['content'] for x in base['files'] if x['path']=='config.json'))
    config.update(case_id=CASE,cell_id='C111603',actor='motor_vehicle_driver',law_id='NRS-484B-307-7a',
                  candidate_id='primary',required_atoms=[],source_packets=[],
                  cameras=[{'name':n,'fps':20} for n in ('overview','approach','reference_corner','driver_reference')],
                  case={'case_id':CASE},supported_case_ids=[CASE],status='unselected_cpu_diagnostic')
    recording={'channels':[{'name':n,'unit':'structured','sampling_rate_hz':20,
                'method':'Retained original-frame synthetic source row','time_window':'30 s / 600 frames',
                'reference_frame':'original frame/time','uncertainty':'50 ms frame bracket; physical and legal review pending'}
                for n in ('ego_request','arrow_request','other_request')],
               'context_inputs':[],
               'limitations':['Synthetic request only; official arrow governance, lawful other traffic, pedestrians and cautiousness unverified']}
    base['recording_description']=recording
    base['files']=[x for x in base['files'] if x['path']!='config.json']
    base['files'].append({'path':'config.json','content':json.dumps(config,indent=2,sort_keys=True)+'\n'})
    base['files'].append({'path':'finalize.py','content':(HERE/'native/finalize_v2.py').read_text()})
    base['status']='unselected_cpu_diagnostic'
    construction=HERE/'current-v2-primary-construction.json';write(construction,base)
    SOURCE.mkdir(parents=True,exist_ok=True)
    (SOURCE/'road.xodr').write_text(road())
    request=rows('yield_then_turn')
    write_rows(SOURCE/'turn-history.jsonl',request)
    write(SOURCE/'arrow-context.json',{'source_kind':'synthetic_cpu_diagnostic',
          'signal_id':'c111603-flashing-yellow-right-arrow-request','official_arrow_verified':False,
          'governs_ego_verified':False,'other_traffic_lawful_status_verified':False,
          'pedestrian_status_verified':False,'physical_cautiousness_verified':False})
    trace,frame_map,evidence,graphs,native_frames=[],[],[],[],[]
    for row in request:
        frame=row['frame'];time=row['time_s'];x,y=row['requested_ego_xy_m'];ox,oy=row['requested_other_xy_m']
        body=[[x+dx,y+dy,z] for dx in (-2,2) for dy in (-.9,.9) for z in (0,1.5)]
        other=[[ox+dx,oy+dy,z] for dx in (-2,2) for dy in (-.9,.9) for z in (0,1.5)]
        speed=0.0 if frame>0 and row['requested_ego_xy_m']==request[frame-1]['requested_ego_xy_m'] else 5.0
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
                      'position_m':[x,y,.5],'heading_deg':row['requested_ego_heading_rad']*180/3.141592653589793,
                      'speed_mps':speed,'speed_mph':speed*2.2369362920544,
                      'control':{'throttle':0,'brake':0,'hand_brake':False}})
        frame_map.append({'carla_frame':frame,'native_frame':frame,'time_s':time,'video_frame':frame})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'ego':{'body_vertices_m':body,'position_m':[x,y,.5],
                                'heading_deg':row['requested_ego_heading_rad']*180/3.141592653589793,
                                'speed_mps':speed,'speed_provenance':'synthetic_native_sample','synthetic_diagnostic':True},
                         'other_actors':[{'actor_id':11,'body_vertices_m':other,'position_m':[ox,oy,.5]}],
                         'replay_frame':frame,'replay_simulation_time_s':time,'actor_id':10,
                         'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':1,'section_id':0,'lane_id':-1,'s_m':y+100}}})
        relative=f'graphs/base/{frame:08d}.adapter.json'
        native_frames.append({'frame':frame,'simulation_time':time,'adapter_graph':relative,
                              'base':relative,'nodes':2,'edges':0})
        graphs.append({'path':'capture/native/'+relative,
                       'attributes':{'frame':frame,'simulation_time_s':time,'synthetic_diagnostic':True,
                                     'source':'C111603 flashing-arrow request diagnostic'},
                       'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':10,
                                 'vertex':[x,y,.5],'forward':[0,1,0],'threedbbox':body}},
                                {'id':'other','attributes':{'sem_class':'vehicle','entity_id':11,
                                  'vertex':[ox,oy,.5],'forward':[1,0,0],'threedbbox':other}}],
                       'edges':[]})
    write_rows(SOURCE/'trace.jsonl',trace);write_rows(SOURCE/'video_frames.jsonl',frame_map)
    write_rows(SOURCE/'capture/evidence.jsonl',evidence)
    write(SOURCE/'capture/manifest.json',{'extraction_confirmed':True,'frames':600,
          'synthetic_diagnostic':True,'sources':{'road.xodr':sha(SOURCE/'road.xodr'),
                                               'trace.jsonl':sha(SOURCE/'trace.jsonl')}})
    spec={'files':{'capture/native/frames.jsonl':''.join(json.dumps(r,separators=(',',':'))+'\n' for r in native_frames),
                   'capture/recorder_info.txt':'synthetic CPU diagnostic; no CARLA recorder\nCreate 10: vehicle.tesla.model3 (0)\nCreate 11: vehicle.audi.a2 (0)\n'},
          'graphs':graphs,
          'videos':[{'path':n+'.mkv','frames':600,'width':1920 if n=='overview' else 1280,
                     'height':1080 if n=='overview' else 720,'fps':20,'color':'black'} for n in
                    ('overview','approach','reference_corner','driver_reference')]}
    spec_path=HERE/'current-v2-primary-fixture-spec.json';write(spec_path,spec)
    sources=[{'path':str(p.relative_to(SOURCE)),'source':str(p.relative_to(REPO)),
              'sha256':sha(p)} for p in sorted(SOURCE.rglob('*')) if p.is_file()]
    recipe=HERE/'current-v2-primary-fixture-recipe.json'
    write(recipe,{'format':'worker-fixture-recipe','sources':sources,
                  'generator':{'source':str(spec_path.relative_to(REPO)),'sha256':sha(spec_path)}})
    contract=HERE/'current-v2-primary-measurement-contract.json'
    write(contract,{'format':'worker-measurement-contract','case_id':CASE,
                    'requirements':[{'disposition_index':0,'requirement':'NRS-484B-307-7a',
                      'source':'NRS 484B.307(7)(a)','output_key':'flashing_arrow_yield_measurement',
                      'method':'measure_turn','value_type':'object','kind':'measured',
                      'inputs':['turn-history.jsonl','arrow-context.json','video_frames.jsonl',
                                'trace.jsonl','capture/evidence.jsonl']}],
                    'negative':{'remove':['turn-history.jsonl'],
                                'error_contains':'Missing required source: turn-history.jsonl'},
                    'status':'unselected_contract_draft'})
    runtime=json.loads((REPO/'batch.json').read_text())
    manifest=HERE/'current-v2-primary-manifest.json'
    write(manifest,{'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':HERE.name,'status':'draft_not_selected',
        'runtime_manifest_sha256':runtime['runtime']['source_manifest_sha256'],
        'cases':[{'case_id':CASE,'kind':'draft_not_selected','id':'primary',
                  'construction':construction.name,'construction_sha256':sha(construction),
                  'fixture_recipe':str(recipe.relative_to(REPO)),
                  'measurement_contract':contract.name,
                  'measurement_procedure':{'entrypoint':'finalize.py'},
                  'recording_description':recording,'candidates':[],
                  'candidate_risk':{'status':'physical','reason':'Official arrow and lawful-traffic status need Native readback'}}]})
    write(HERE/'proposals/cases.json',{'format':'worker-case-proposals','cases':[{
          'case_id':CASE,'target_law_id':'NRS-484B-307-7a','target_type':'attempt',
          'rationale':'Unselected flashing-arrow other-traffic yield timing diagnostic',
          'variable_assignments':{'requested_other_inside_at_entry':False},
          'recording_description':recording}]})
    print(json.dumps({'manifest_sha256':sha(manifest),'recipe_sha256':sha(recipe),
                      'construction_sha256':sha(construction)}))
if __name__=='__main__':main()
