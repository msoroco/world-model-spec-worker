"""Materialize exact exclusion-branch constructions for CPU proof execution."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
REPO=BASE.parents[1]
CASE_SUFFIXES=('device_controlled','opposing_no_turn','opposing_left_turn')
CANDIDATES=('primary','fallback2')
MODULES={'native/build.py':'native_build_module.py',
         'native/check.py':'native_check_module.py',
         'native/capture.py':'native_capture_module.py',
         'native/assemble_original.py':'native_assemble_original_module.py',
         'native/process_original.py':'native_process_original_module.py'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')


def source_ref(path,content=None):
    return {'path':path,'content':content}


def build(suffix,candidate):
    if suffix not in CASE_SUFFIXES or candidate not in CANDIDATES:
        raise ValueError('Unknown selected branch candidate')
    case_id=BASE.name+'__'+suffix
    draft=HERE/suffix/candidate/'native-request'
    baseline=json.loads((BASE/'selected-v5/controlled_2/primary/construction.json').read_text())
    source_files={item['path']:item['content'] for item in baseline['files']}
    config=json.loads((draft/'config.json').read_text())
    config.update(cell_id='C111294',actor='motor_vehicle_driver',law_id='NRS-484B-250-2',
                  required_atoms=[],source_packets=[],selected_case_id=case_id,
                  duration_s=30,cameras=json.loads(source_files['config.json'])['cameras'],
                  case={'case_id':case_id},supported_case_ids=[case_id],
                  status='selected_cpu_prepared_original_unverified')
    construction={key:baseline[key] for key in
                  ('actor','cell_id','entrypoint','law_id','measurement_plan',
                   'mechanisms','recording_description','static_checks','status','termination_rules')}
    construction['case_id']=case_id
    construction['mechanisms']={
        'actors':'Original CARLA ego and other vehicle; branch request retained separately from measured motion',
        'road':'Crossed authored highways with '+suffix+' statutory context',
        'capture':'Four synchronized RGB views, original actor bodies and map/device inventory',
        'construction_status':'selected_cpu_prepared_original_unverified'}
    construction['static_checks']=[
        {'name':'source_joined_branch_request','status':'passed_cpu_request'},
        {'name':'original_world_lane_device_and_turn','status':'pending_original_capture'}]
    construction['measurement_plan']={**baseline['measurement_plan'],
        'branch_context':suffix,
        'method':'Retain source-joined actor-body entry, exit, device count, opposing direction and turn request'}
    files=[]
    for name in ('assignment-source.json','case-plan.json','crossroads.xodr','requested-tracks.jsonl'):
        files.append(source_ref(name,(draft/name).read_text()))
    for path,source in MODULES.items():
        files.append(source_ref('work/'+BASE.name+'/'+path,(HERE/source).read_text()))
    files.append(source_ref('config.json',json.dumps(config,indent=2,sort_keys=True)+'\n'))
    finalizer=(HERE/'finalize_branch.py').read_text().replace('__CASE__',case_id).replace('__BRANCH__',suffix)
    files.append(source_ref('finalize.py',finalizer))
    files.append(source_ref('runner.py',source_files['runner.py']))
    files.append(source_ref('tests/test_exact.py',(HERE/'test_materialized.py').read_text()))
    construction['files']=files
    path=HERE/suffix/candidate/'construction.json'
    put(path,construction)
    return {'case_id':case_id,'candidate':candidate,'construction_sha256':sha(path)}


if __name__=='__main__':
    print(json.dumps([build(suffix,candidate)
                      for suffix in CASE_SUFFIXES for candidate in CANDIDATES]))
