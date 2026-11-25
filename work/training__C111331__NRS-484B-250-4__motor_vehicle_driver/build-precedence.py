"""Build three source-isolated marked-line precedence requests and CPU fixtures."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
BASE=HERE.name
SPECS={'prior_stop_yield':470,'prior_stop_no_yield':140,'inside_vehicle_no_yield':270}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in rows))


def request(frame,release):
    ego=-35+.05*min(frame,130)+.1*max(0,frame-release)
    other=-35+.05*min(frame,130)+.2*max(0,frame-200)
    phase='approach' if frame<130 else 'hold_pre_line' if frame<=release else 'post_stop_entry_request'
    other_phase='approach' if frame<130 else 'hold_pre_line' if frame<=200 else 'entry_request'
    return {'frame':frame,'time_s':frame/20,'source_kind':'construction_request','native_observed':False,
      'ego_center_xy_m':[round(ego,6),-1.75],'ego_front_x_m':round(ego+2,6),
      'other_center_xy_m':[1.75,round(other,6)],'ego_phase_requested':phase,
      'other_phase_requested':other_phase,'marked_stop_line_x_m':-26.0,
      'other_marked_stop_line_y_m':-26.0,'near_side_crosswalk_x_m':-23.0,
      'intersection_entry_x_m':-20.0,'signal_state_requested':'Off',
      'signal_id':'c111331-installed-uncovered-vehicular-head',
      'signal_installed_requested':True,'signal_uncovered_requested':True,
      'signal_display_requested':'inoperative_dark','legal_verdict':None}


def sources(suffix,rows):
    root=HERE/'precedence'/suffix/'sources';root.mkdir(parents=True,exist_ok=True)
    (root/'road.xodr').write_bytes((HERE/'selected-road.xodr').read_bytes())
    write_rows(root/'vehicle-history.jsonl',rows)
    write(root/'signal-context.json',{'source_kind':'synthetic_cpu_diagnostic',
      'signal_id':'c111331-installed-uncovered-vehicular-head',
      'official_signal_state_verified':False,'marked_stop_line_x_m':-26,
      'near_side_crosswalk_x_m':-23,'intersection_entry_x_m':-20,
      'physical_stop_verified':False,'yielding_verified':False})
    trace=[];maps=[];evidence=[];graphs=[];native=[]
    for row in rows:
        i=row['frame'];t=row['time_s'];x,y=row['ego_center_xy_m'];ox,oy=row['other_center_xy_m']
        body=[[x+dx,y+dy,z] for dx in (-2,2) for dy in (-.9,.9) for z in (0,1.5)]
        other=[[ox+dy,oy+dx,z] for dx in (-2,2) for dy in (-.9,.9) for z in (0,1.5)]
        speed=0 if i and row['ego_center_xy_m']==rows[i-1]['ego_center_xy_m'] else 2.0
        trace.append({'frame':i,'time_s':t,'position':{'x':x,'y':y,'z':.5},
          'position_m':[x,y,.5],'heading_deg':0,'speed_mps':speed,
          'speed_mph':speed*2.2369362920544,'velocity_mps':[speed,0,0],
          'control':{'throttle':0,'brake':0,'hand_brake':False}})
        maps.append({'carla_frame':i,'native_frame':i,'time_s':t,'video_frame':i})
        evidence.append({'original_frame':i,'recording_time_s':t,
          'ego':{'body_vertices_m':body,'position_m':[x,y,.5],'heading_deg':0,
                 'speed_mps':speed,'speed_provenance':'synthetic_native_sample','synthetic_diagnostic':True},
          'other_actors':[{'actor_id':11,'body_vertices_m':other,'position_m':[ox,oy,.5]}],
          'replay_frame':i,'replay_simulation_time_s':t,'actor_id':10,
          'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
          'road_projection':{'road_id':250,'section_id':0,'lane_id':-1,'s_m':x+100}}})
        rel=f'graphs/base/{i:08d}.adapter.json'
        native.append({'frame':i,'simulation_time':t,'adapter_graph':rel,'base':rel,'nodes':2,'edges':0})
        graphs.append({'path':'capture/native/'+rel,
          'attributes':{'frame':i,'simulation_time_s':t,'synthetic_diagnostic':True,
                        'source':'C111331 precedence request diagnostic'},
          'nodes':[{'id':'ego','attributes':{'sem_class':'ego','entity_id':10,
                    'vertex':[x,y,.5],'forward':[1,0,0],'threedbbox':body}},
                   {'id':'other','attributes':{'sem_class':'vehicle','entity_id':11,
                    'vertex':[ox,oy,.5],'forward':[0,1,0],'threedbbox':other}}],
          'edges':[]})
    write_rows(root/'trace.jsonl',trace);write_rows(root/'video_frames.jsonl',maps)
    write_rows(root/'capture/evidence.jsonl',evidence)
    write(root/'capture/manifest.json',{'extraction_confirmed':True,'frames':600,
      'synthetic_diagnostic':True,'sources':{'road.xodr':sha(root/'road.xodr'),
                                           'trace.jsonl':sha(root/'trace.jsonl')}})
    spec={'files':{'capture/native/frames.jsonl':''.join(json.dumps(r,separators=(',',':'))+'\n' for r in native),
       'capture/recorder_info.txt':'synthetic CPU diagnostic; no CARLA recorder\nCreate 10: vehicle.tesla.model3 (0)\nCreate 11: vehicle.audi.a2 (0)\n'},
       'graphs':graphs,'videos':[{'path':n+'.mkv','frames':600,
           'width':1920 if n=='overview' else 1280,'height':1080 if n=='overview' else 720,
           'fps':20,'color':'black'} for n in ('overview','approach','reference_corner','driver_reference')]}
    spec_path=HERE/'precedence'/suffix/'fixture-spec.json';write(spec_path,spec)
    paths=[{'path':str(p.relative_to(root)),'source':str(p.relative_to(REPO)),
            'sha256':sha(p)} for p in sorted(root.rglob('*')) if p.is_file() and p.name!='road.xodr']
    recipe=HERE/'precedence'/suffix/'fixture-recipe.json'
    write(recipe,{'format':'worker-fixture-recipe','sources':paths,
                  'generator':{'source':str(spec_path.relative_to(REPO)),'sha256':sha(spec_path)}})
    return recipe


def construction(suffix,rows,candidate,shift):
    template=json.loads((HERE/'selected-candidates/controlled_1/primary/construction.json').read_text())
    item=copy.deepcopy(template);case=BASE+'__'+suffix;item['case_id']=case
    for f in item['files']:
        if f['path']=='config.json':
            config=json.loads(f['content']);config.update(case_id=case,case={'case_id':case},
              supported_case_ids=[case],candidate_id=candidate,spawn_shift_m=shift)
            f['content']=json.dumps(config,indent=2,sort_keys=True)+'\n'
        elif f['path']=='request.jsonl':f['content']=''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows)
        elif f['path']=='runner.py':
            start=f['content'].index("    if cfg['case_id'].endswith('controlled_1'):")
            end=f['content'].index("    return {'case_id':",start)
            f['content']=f['content'][:start]+"    assert any(rows[i]['ego_center_xy_m']==rows[i-1]['ego_center_xy_m'] and rows[i]['ego_front_x_m'] < -26 for i in range(1,600))\n"+f['content'][end:]
        elif f['path']=='finalize.py':
            f['content']=f['content'].replace(BASE+'__controlled_1',case)
            if suffix in ('prior_stop_yield','inside_vehicle_no_yield'):
                f['content']=f['content'].replace("'sources':{name:sha(attempt/name) for name in SOURCES}}},\n            'source_complete'",
                    "'sources':{name:sha(attempt/name) for name in SOURCES}},\n            'inoperative_signal_inside_measurement':{'method':'measure_stop','value':metric,'sources':{name:sha(attempt/name) for name in SOURCES}}},\n            'source_complete'")
        elif f['path']=='capture_selected.py':
            f['content']=f['content'].replace("else 2.0\n", "else 4.0 if other else 2.0\n")
    dest=HERE/'precedence'/suffix/candidate/'construction.json';write(dest,item)
    return dest


def main():
    manifest=json.loads((HERE/'selected-construction-manifest.json').read_text())
    existing={r['case_id'] for r in manifest['cases']}
    for suffix,release in SPECS.items():
        case=BASE+'__'+suffix
        if case in existing:raise ValueError('Precedence case already in selected manifest')
        rows=[request(i,release) for i in range(600)]
        if not any(r['ego_front_x_m']<-26 and r['ego_phase_requested']=='hold_pre_line' for r in rows):
            raise ValueError('Pre-line halt request missing')
        recipe=sources(suffix,rows)
        entries=[]
        for candidate,shift in (('primary',0),('fallback1',2.0)):
            path=construction(suffix,rows,candidate,shift)
            entries.append((candidate,path.relative_to(HERE).as_posix(),sha(path)))
        entry={'case_id':case,'id':suffix,'kind':'draft_not_selected',
               'construction':entries[0][1],'construction_sha256':entries[0][2],
               'fixture_recipe':str(recipe.relative_to(REPO)),
               'measurement_contract':f'precedence/{suffix}/measurement-contract.json',
               'measurement_procedure':{'entrypoint':'finalize.py'},
               'candidate_risk':{'status':'physical','reason':'Primary ego spawn may be obstructed on Native map import'},
               'candidates':[{'id':'fallback1','construction':entries[1][1],
                   'construction_sha256':entries[1][2],
                   'changed_knobs':['spawn_shift_m: 0 to 2.0'],
                   'trigger':{'source':'native-map-readback.json and capture report',
                              'metric':'ego approach spawn clearance',
                              'failure_condition':'Primary spawn obstructed or outside lane'}}]}
        indices=[3,4] if suffix=='prior_stop_yield' else [3] if suffix=='prior_stop_no_yield' else [4]
        write(HERE/'precedence'/suffix/'measurement-contract.json',{'format':'worker-measurement-contract',
            'case_id':case,'requirements':[{'disposition_index':index,
            'requirement':'NRS-484B-250-4','source':'NRS 484B.250(4)',
            'output_key':'inoperative_signal_stop_measurement' if index==3 else 'inoperative_signal_inside_measurement',
            'method':'measure_stop','value_type':'object','kind':'measured',
            'inputs':['vehicle-history.jsonl','signal-context.json','video_frames.jsonl',
                      'trace.jsonl','capture/evidence.jsonl']} for index in indices],
            'negative':{'remove':['vehicle-history.jsonl'],
                        'error_contains':'Missing required source: vehicle-history.jsonl'},
            'status':'unselected_contract_draft'})
        manifest['cases'].append(entry)
    manifest['status']='selected_cpu_precedence_construction_in_progress'
    write(HERE/'precedence-construction-manifest.json',manifest)

if __name__=='__main__':main()
