"""Build exact scooter case bundles and source-hashed diagnostic recipes."""
import hashlib
import json
from pathlib import Path
from package_spec import ACTOR,AID,CAMERAS,CELL,LAW,RECORDING
from scooter_785 import CASES,SOURCE_ROLES
from tests.test_bundle import scene_for


HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
EXAMPLE=ROOT/'runtime/fixtures/example.json'
RUNTIME_MANIFEST=ROOT/'runtime/SOURCE-MANIFEST.json'
PACKAGE_FILES=('runner.py','analysis.py','package_spec.py','scooter_785.py',
               'scooter_adapter.py','scooter_capture.py','tests/test_bundle.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path,value,compact=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    options={'separators':(',',':')} if compact else {'indent':2}
    path.write_text(json.dumps(value,ensure_ascii=False,**options)+'\n')
    if path.stat().st_size > 2*1024*1024:
        raise ValueError('scooter returned source exceeds 2 MiB: '+str(path))


def config_for(case):
    cid=AID+'__'+case.name
    return {'assignment_id':AID,'law_id':LAW,'cell_id':CELL,'actor':ACTOR,
            'selected_case_id':cid,'candidate_id':'primary',
            'rate_hz':20,'duration_s':45,'required_atoms':[],'source_packets':[],
            'cameras':CAMERAS,'supported_case_ids':[AID+'__'+x.name for x in CASES],
            'engineering_profile':{'spawn_z_adjust_m':0},
            'requested_speed_mps':case.speed_mph*.44704,
            'case':{'case_id':cid,'target_law_id':LAW,'kind':'delivery',
                    'new_capture_selected':True,'gap_ids':['gap-no-accepted-evidence'],
                    'requested_speed_mph':case.speed_mph,
                    'ordinance_context':case.ordinance,
                    'qualifying_scooter':case.qualifies,
                    'bicycle_lane_occupancy':case.in_lane,
                    'recording_description':RECORDING}}


def construction_for(case,config):
    cid=AID+'__'+case.name
    files=[{'path':name,'source':str((HERE/name).relative_to(ROOT)),
            'content':(HERE/name).read_text()} for name in PACKAGE_FILES]
    files.append({'path':'config.json','content':json.dumps(config,indent=2)+'\n'})
    return {'law_id':LAW,'cell_id':CELL,'actor':ACTOR,'case_id':cid,
            'entrypoint':'runner.py','recording_description':RECORDING,
            'files':files,'measurement_plan':{'method':'analysis.py:analyze',
                      'source':'original source receipt, device/lane/ordinance packet and 20 Hz Native body/velocity history',
                      'statutory_boundary_mph':15,'legal_verdict_claimed':False},
            'static_checks':['exact assignment and case','official lane and device source hashes',
                             '900 joined original frames','four camera streams'],
            'termination_rules':['900 original frames or preserved physical failure'],
            'mechanisms':{'scooter':'source-certified original asset with reviewed characteristics',
                          'lane':'official polygon and actual body-corner occupancy',
                          'speed':'target velocity with original velocity readback',
                          'ordinance':'official source identity and unresolved effect'}}


def fixture_for(case):
    cid=AID+'__'+case.name
    scene=scene_for(case)
    scene['lane_designation_id']='synthetic-diagnostic-lane'
    scene['jurisdiction']='synthetic-diagnostic-jurisdiction'
    base=json.loads(EXAMPLE.read_text())
    trace=[json.loads(line) for line in base['files']['trace.jsonl'].splitlines()]
    mapping=[json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    capture=[json.loads(line) for line in base['files']['capture/evidence.jsonl'].splitlines()]
    rows=[]
    y=1.75
    for index,(t,m,e) in enumerate(zip(trace,mapping,capture)):
        x=t['position_m'][0]
        y=t['position_m'][1]
        t['speed_mps']=case.speed_mph*.44704
        t['speed_mph']=case.speed_mph
        e['ego']['speed_mps']=t['speed_mps']
        rows.append({'frame':index,'native_frame':m['carla_frame'],
                     'original_frame':m['carla_frame'],'time_s':m['time_s'],
                     'native_actor_id':'synthetic-scooter-1',
                     'device_id':scene['device']['device_id'],
                     'body_corners_xy':[[x-.3,y-.3],[x-.3,y+.3],[x+.3,y+.3],[x+.3,y-.3]],
                     'position_xyz_m':t['position_m'],
                     'heading_deg':0,'speed_mps':t['speed_mps'],
                     **{role+'_source_sha256':scene[role+'_source_sha256'] for role in SOURCE_ROLES}})
    base['files']['trace.jsonl']=''.join(json.dumps(t,sort_keys=True)+'\n' for t in trace)
    base['files']['capture/evidence.jsonl']=''.join(json.dumps(e,sort_keys=True)+'\n' for e in capture)
    capture_manifest=json.loads(base['files']['capture/manifest.json'])
    capture_manifest['case_id']=cid
    capture_manifest['sources']['trace.jsonl']=hashlib.sha256(base['files']['trace.jsonl'].encode()).hexdigest()
    base['files']['capture/manifest.json']=json.dumps(capture_manifest,sort_keys=True)+'\n'
    history={'source_kind':'synthetic_diagnostic_fixture','assignment_id':AID,
             'case_id':cid,'reviewed_site_sha256':'a'*64,'map_sha256':'b'*64,
             'scene':scene,'native_actor_id':'synthetic-scooter-1','samples':rows}
    base['files']['scooter-history.json']=json.dumps(history,sort_keys=True)+'\n'
    receipt={'source_kind':'synthetic_diagnostic_fixture','diagnostic_fixture':True,
             'case_id':cid,'physical_acceptance':False,'legal_verdict':None,
             'history_sha256':hashlib.sha256(base['files']['scooter-history.json'].encode()).hexdigest(),
             'trace_sha256':hashlib.sha256(base['files']['trace.jsonl'].encode()).hexdigest(),
             'frame_map_sha256':hashlib.sha256(base['files']['video_frames.jsonl'].encode()).hexdigest()}
    base['files']['original-source-receipt.json']=json.dumps(receipt,sort_keys=True)+'\n'
    generator=HERE/'diagnostics'/(case.name+'-generator.json')
    put(generator,base,compact=True)
    recipe=HERE/'diagnostics'/(case.name+'-recipe.json')
    put(recipe,{'format':'worker-fixture-recipe','sources':[
        {'path':'diagnostic-input.json','source':'runtime/fixtures/example.json','sha256':sha(EXAMPLE)}],
        'generator':{'source':str(generator.relative_to(ROOT)),'sha256':sha(generator)}})
    plan=json.loads((HERE/'case-plan.json').read_text())
    keys=('scooter_qualification','bicycle_lane_occupancy','speed_history_mph','ordinance_context')
    inputs=['scooter-history.json','original-source-receipt.json','trace.jsonl','video_frames.jsonl']
    contract=HERE/'diagnostics'/(case.name+'-measurement-contract.json')
    put(contract,{'format':'worker-measurement-contract','case_id':cid,
                  'requirements':[{'disposition_index':i,'requirement':d['requirement'],
                                   'source':d['source'],'output_key':keys[i],
                                   'method':'source_sealed_scooter_measurement',
                                   'value_type':'object','kind':'measured','inputs':inputs}
                                  for i,d in enumerate(plan['requirement_dispositions'])],
                  'negative':{'remove':['scooter-history.json'],
                              'error_contains':'Missing required source: scooter-history.json'}})
    return recipe,contract


def build():
    cases=[]
    for index,case in enumerate(CASES):
        config=config_for(case)
        bundle=HERE/'cases'/case.name
        put(bundle/'config.json',config)
        if index==0:
            put(HERE/'config.json',config)
        primary=construction_for(case,config)
        put(bundle/'construction.json',primary)
        if index==0:
            put(HERE/'construction.json',primary)
        fallback_config=json.loads(json.dumps(config))
        fallback_config['engineering_profile']['spawn_z_adjust_m']=.08
        fallback=construction_for(case,fallback_config)
        put(bundle/'fallback1-construction.json',fallback)
        recipe,contract=fixture_for(case)
        cases.append({'case_id':AID+'__'+case.name,'kind':'delivery',
                      'construction':str((bundle/'construction.json').relative_to(HERE)),
                      'construction_sha256':sha(bundle/'construction.json'),
                      'candidate_risk':{'status':'physical',
                          'reason':'Original scooter asset may fail at the surveyed spawn height; an 8 cm vertical adjustment preserves route, speed, designation and source context.'},
                      'candidates':[{'id':'fallback1',
                         'construction':str((bundle/'fallback1-construction.json').relative_to(HERE)),
                         'construction_sha256':sha(bundle/'fallback1-construction.json'),
                         'trigger':{'source':'Native spawn readback and original body geometry',
                                    'metric':'source-certified scooter spawn and initial body-road contact',
                                    'failure_condition':'primary spawn fails or initial body-road contact is invalid'},
                         'changed_knobs':['spawn_z_adjust_m: +0.08 m']}],
                      'fixture_recipe':str(recipe.relative_to(ROOT)),
                      'measurement_contract':str(contract.relative_to(HERE)),
                      'measurement_procedure':{'entrypoint':'analysis.py',
                                               'method':'source-sealed original scooter device, lane, velocity and ordinance context'},
                      'native_handoff':{'python_env_var':'CARLA_PYTHON',
                                        'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT',
                                        'reviewed_packet_env_var':'C230223_7851A_REVIEWED_SITE'},
                      'acquisition':{name:{'entrypoint':'runner.py' if name in ('scooter_device_identity','bicycle_lane_designation','ordinance_applicability') else 'scooter_capture.py',
                                           'method':method,'evidence':'original-source-receipt.json, scooter-history.json and four synchronized videos'}
                                     for name,unit,method in [('scooter_device_identity','', 'reviewed original device specification'),
                                                              ('bicycle_lane_designation','','official designation and geometry'),
                                                              ('ego_body_lane_occupancy','','original body-corner geometry'),
                                                              ('ego_speed_mph','','Native original velocity magnitude'),
                                                              ('ordinance_applicability','','official ordinance source'),
                                                              ('original_frame_join','','Native frame/map/video identity')]}})
    put(HERE/'execution-manifest.draft.json',{'format':'worker-execution-manifest',
         'assignment_id':AID,'runtime_manifest_sha256':sha(RUNTIME_MANIFEST),
         'cases':cases})
    print('built scooter cases',len(cases))


if __name__=='__main__':
    build()
