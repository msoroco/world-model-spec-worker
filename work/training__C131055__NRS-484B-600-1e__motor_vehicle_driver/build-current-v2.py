"""Build two exact retained-source 600-frame roundabout speed CPU diagnostics."""
import hashlib
import json
import math
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from geometry import open_drive,ARC_M,check as check_geometry
from runner import check as check_runner

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def rows(p,items):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in items))
def build(label,index,high):
    case=HERE.name+f'__controlled_{index}'
    base=json.loads((HERE/'draft-roundabout/above_80_request/primary/construction.json').read_text())
    config=json.loads(next(x['content'] for x in base['files'] if x['path']=='config.json'))
    config.update(case_id=case,selected_case_id=case,supported_case_ids=[case],candidate_id='primary',
                  cell_id='C131055',actor='motor_vehicle_driver',required_atoms=[],source_packets=[],
                  case={'case_id':case},status='unselected_cpu_diagnostic',
                  cameras=[{'name':n,'fps':20} for n in ('overview','approach','reference_corner','driver_reference')])
    record={'channels':[{'name':'original_vehicle_velocity_position','unit':'structured','sampling_rate_hz':20,
             'method':'Retained original-frame synthetic source row','time_window':'30 s / 600 frames',
             'reference_frame':'original frame/time and surveyed arc/exit','uncertainty':'50 ms frame bracket; Native review pending'}],
            'context_inputs':[],'limitations':['Synthetic source only; actual Native speed and lane retention unverified']}
    base['case_id']=case;base['recording_description']=record;base['status']='unselected_cpu_diagnostic'
    base['files']=[x for x in base['files'] if x['path']!='config.json']
    base['files'].append({'path':'config.json','content':json.dumps(config,indent=2,sort_keys=True)+'\n'})
    base['files'].append({'path':'finalize.py','content':(HERE/'native/finalize_v2.py').read_text()})
    construction=HERE/f'current-v2-{label}-construction.json';write(construction,base)
    source=HERE/f'current-v2-{label}-sources';source.mkdir(parents=True,exist_ok=True)
    (source/'road.xodr').write_text(open_drive()+'\n')
    survey=[]
    for road,s in ((1,ARC_M-100),(1,ARC_M-10),(2,20),(2,300)):
        for lane in (-1,-2):survey.append({'road_id':road,'lane_id':lane,'s_m':s,'native_xyz_m':[s,-500,0]})
    write(source/'roundabout-survey.json',survey)
    history,trace,mapping,evidence,graphs,native=[],[],[],[],[],[]
    for i in range(600):
        t=i/20;road=1 if i<500 else 2
        speed=38.0 if high and i>=500 else 29.0
        if road==1:
            angle=(i/500)*math.pi/2;x=-500+500*(1-math.cos(angle));y=-500*math.sin(angle)
        else:x=(i-500)*1.5;y=-500.0
        x,y=round(x,6),round(y,6)
        body=[[x+dx,y+dy,z] for dx in (-2,2) for dy in (-.9,.9) for z in (0,1.5)]
        history.append({'video_frame':i,'native_frame':i,'time_s':t,'subject_id':10,
          'position_xyz_m':[x,y,.5],'velocity_xyz_mps':[speed,0,0],'road_id':road,'lane_id':-2,
          'synthetic_diagnostic':True})
        trace.append({'frame':i,'time_s':t,'position':{'x':x,'y':y,'z':.5},'position_m':[x,y,.5],
          'heading_deg':0,'velocity_mps':[speed,0,0],'speed_mps':speed,'speed_mph':speed*2.2369362920544,
          'control':{'throttle':0,'brake':0,'hand_brake':False}})
        mapping.append({'carla_frame':i,'native_frame':i,'time_s':t,'video_frame':i})
        evidence.append({'original_frame':i,'recording_time_s':t,'ego':{'body_vertices_m':body,
          'position_m':[x,y,.5],'heading_deg':0,'speed_mps':speed,
          'speed_provenance':'synthetic_native_sample','synthetic_diagnostic':True},
          'other_actors':[],'replay_frame':i,'replay_simulation_time_s':t,'actor_id':10,
          'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                   'road_projection':{'road_id':road,'section_id':0,'lane_id':-2,'s_m':(ARC_M-100)+i*1.5 if road==1 else (i-500)*1.5}}})
        rel=f'graphs/base/{i:08d}.adapter.json'
        native.append({'frame':i,'simulation_time':t,'adapter_graph':rel,'base':rel,'nodes':1,'edges':0})
        graphs.append({'path':'capture/native/'+rel,'attributes':{'frame':i,'simulation_time_s':t,
          'synthetic_diagnostic':True,'source':'C131055 roundabout speed CPU diagnostic'},
          'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':10,'vertex':[x,y,.5],
                   'forward':[1,0,0],'threedbbox':body}}],'edges':[]})
    rows(source/'roundabout-speed-history.jsonl',history)
    rows(source/'trace.jsonl',trace);rows(source/'video_frames.jsonl',mapping)
    rows(source/'capture/evidence.jsonl',evidence)
    write(source/'capture/manifest.json',{'extraction_confirmed':True,'frames':600,
      'synthetic_diagnostic':True,'sources':{'road.xodr':sha(source/'road.xodr'),
                                            'trace.jsonl':sha(source/'trace.jsonl')}})
    spec={'files':{'capture/native/frames.jsonl':''.join(json.dumps(r,separators=(',',':'))+'\n' for r in native),
                   'capture/recorder_info.txt':'synthetic CPU diagnostic; no CARLA recorder\nCreate 10: vehicle.tesla.model3 (0)\n'},
          'graphs':graphs,'videos':[{'path':n+'.mkv','frames':600,'width':1920 if n=='overview' else 1280,'height':1080 if n=='overview' else 720,
                                    'fps':20,'color':'black'} for n in
                                   ('overview','approach','reference_corner','driver_reference')]}
    specp=HERE/f'current-v2-{label}-fixture-spec.json';write(specp,spec)
    recipe=HERE/f'current-v2-{label}-fixture-recipe.json'
    source_rows=[{'path':str(p.relative_to(source)),'source':str(p.relative_to(REPO)),
                  'sha256':sha(p)} for p in sorted(source.rglob('*')) if p.is_file()]
    write(recipe,{'format':'worker-fixture-recipe','sources':source_rows,
                  'generator':{'source':str(specp.relative_to(REPO)),'sha256':sha(specp)}})
    contract=HERE/f'current-v2-{label}-measurement-contract.json'
    write(contract,{'format':'worker-measurement-contract','case_id':case,
      'requirements':[{'disposition_index':0,'requirement':'NRS-484B-600-1e',
        'source':'NRS 484B.600(1)(e)','output_key':'roundabout_speed_measurement',
        'method':'measure_speed','value_type':'object','kind':'measured',
        'inputs':['roundabout-speed-history.jsonl','roundabout-survey.json','video_frames.jsonl',
                  'trace.jsonl','capture/evidence.jsonl']}],
      'negative':{'remove':['roundabout-speed-history.jsonl'],
                  'error_contains':'Missing required source: roundabout-speed-history.jsonl'},
      'status':'unselected_contract_draft'})
    batch=json.loads((REPO/'batch.json').read_text())
    manifest=HERE/f'current-v2-{label}-manifest.json'
    write(manifest,{'format':'worker-unselected-draft-construction-manifest-v1',
      'assignment_id':HERE.name,'status':'draft_not_selected',
      'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
      'cases':[{'case_id':case,'kind':'draft_not_selected','id':'primary','construction':construction.name,
        'construction_sha256':sha(construction),'fixture_recipe':str(recipe.relative_to(REPO)),
        'measurement_contract':contract.name,'measurement_procedure':{'entrypoint':'finalize.py'},
        'recording_description':record,'candidates':[],
        'candidate_risk':{'status':'physical','reason':'Actual high-speed arc/exit lane retention needs Native readback'}}]})
    return {'case_id':case,'manifest_sha256':sha(manifest),'construction_sha256':sha(construction),'recipe_sha256':sha(recipe)}
def main():
    check_geometry();check_runner()
    proofs=[build('below',1,False),build('above',2,True)]
    write(HERE/'proposals/cases.json',{'format':'worker-case-proposals','cases':[{'case_id':p['case_id'],
      'target_law_id':'NRS-484B-600-1e','target_type':'attempt',
      'rationale':'Unselected roundabout speed CPU diagnostic','variable_assignments':{'requested_speed_mps':29 if i==0 else 38}}
      for i,p in enumerate(proofs)]})
    print(json.dumps(proofs))
if __name__=='__main__':main()
