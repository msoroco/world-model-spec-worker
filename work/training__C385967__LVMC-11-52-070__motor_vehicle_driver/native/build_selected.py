"""Bind exact selected C385967 construction and source-measurement contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
FOLDER=HERE.parent
ROOT=FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def main():
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    draft=json.loads((HERE/'selected-draft-manifest.json').read_text())
    proposals=[];entries=[]
    for suffix,yaw in (('a',45),('b',225)):
        case=FOLDER.name+'__probe_'+suffix
        item=next(e for e in draft['cases'] if e['case_id']==case)
        construction=json.loads((HERE/item['construction']).read_text())
        description=construction['recording_description']
        proposals.append({'case_id':case,'target_law_id':'LVMC-11-52-070',
            'target_type':'boundary_probe',
            'rationale':'Compare parked front relative to lawful one-way traffic with separate City permission source',
            'variable_assignments':{
                'requested_front_yaw_deg':{'kind':'controller','value':yaw,'unit':'deg'},
                'observed_front_direction':{'kind':'subject_behavior','value':None,'unit':'categorical'},
                'one_way_road':{'kind':'world_setup','value':True,'unit':'boolean'}},
            'unresolved_judgment_calls':['City Traffic Engineer street designation and actual marking require independent review'],
            'recording_description':description,
            'paired_probe_id':'LVMC-11-52-070@motor_vehicle_driver:angle_park_orientation',
            'deliberate_differences':['requested_front_yaw_deg'],
            'probe':{'primary_variable':'observed_front_direction',
                'comparison_or_standard':'LVMC 11.52.070 front toward lawful traffic direction',
                'target_value_or_branch':('with_flow' if suffix=='a' else 'against_flow'),
                'test_value':('with_flow' if suffix=='a' else 'against_flow'),
                'operator':'categorical','unit':'categorical'}})
        contract={'format':'worker-measurement-contract','case_id':case,
            'requirements':[{'disposition_index':0,
                'requirement':plan['requirement_dispositions'][0]['requirement'],
                'source':plan['requirement_dispositions'][0]['source'],
                'output_key':'parked_front_direction',
                'method':'measure_parked_front_direction','value_type':'text',
                'kind':'measured','inputs':['native_samples.jsonl','video_frames.jsonl',
                    'body_history.jsonl','road_geometry.json','parking_context.json',
                    'permission_authority.json','permission-source.bin']}],
            'negative':{'remove':['permission_authority.json'],
                        'error_contains':'Missing required source: permission_authority.json'}}
        write(HERE/f'selected-{suffix}-measurement-contract.json',contract)
        config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
        required=set(config['required_atoms'])|{channel['name'] for channel in description['channels']}
        acquisition={name:{'entrypoint':'capture.py' if name in config['required_atoms'] else 'finalize.py',
            'method':'source-joined original Native sample, context or saved diagnostic',
            'evidence':'native_samples.jsonl and channels/'+name+'.jsonl'} for name in sorted(required)}
        fall=item['candidates'][0]
        fallback={'id':'fallback1','construction':'native/'+fall['construction'],
            'construction_sha256':fall['construction_sha256'],
            'trigger':{'metric':'maximum_original_parking_speed_mps',
                'failure_condition':'observed at-rest speed exceeds engineering 0.1 m/s diagnostic',
                'source':'original Native native_samples.jsonl ego_speed_mps'},
            'changed_knobs':['parking_brake_mode'],
            'offline':{'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{FOLDER.name}/native/selected-draft-manifest.json --case {case} --candidate fallback1 --output .runtime-work/c385967-offline3-{suffix}-fallback1',
                'exit_code':0,'construction_sha256':fall['construction_sha256'],
                'log':f'native/selected-{suffix}-fallback1-offline.log',
                'log_sha256':sha(HERE/f'selected-{suffix}-fallback1-offline.log')},
            'compatibility':{}}
        physical=HERE/f'physical-{suffix}-receipt.json'
        entries.append({'case_id':case,'kind':'delivery','id':'primary',
            'construction':'native/'+item['construction'],
            'construction_sha256':item['construction_sha256'],
            'candidate_risk':{'status':'physical','reason':
                'Original Native parked body containment and at-rest speed require measurement'},
            'candidates':[fallback],
            'measurement_contract':f'native/selected-{suffix}-measurement-contract.json',
            'measurement_procedure':{'entrypoint':'finalize.py','status':'saved_source_diagnostic'},
            'fixture_recipe':f'work/{FOLDER.name}/native/selected-{suffix}-fixture-recipe.json',
            'physical_preparation':{'receipt':f'native/{physical.name}',
                'sha256':sha(physical),'scope':'synthetic CPU triad; original unverified'},
            'offline':{'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{FOLDER.name}/native/selected-draft-manifest.json --case {case} --candidate primary --output .runtime-work/c385967-offline3-{suffix}-primary',
                'exit_code':0,'construction_sha256':item['construction_sha256'],
                'log':f'native/selected-{suffix}-primary-offline.log',
                'log_sha256':sha(HERE/f'selected-{suffix}-primary-offline.log')},
            'native_handoff':{'python_env_var':'CARLA_PYTHON',
                'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},
            'acquisition':acquisition,'negative':{'log':f'native/selected-{suffix}-primary-negative.log'},
            'compatibility':{},'delivery_acceptance':{},'post_capture':{}})
    baseline=dict(proposals[0])
    baseline.update(case_id=FOLDER.name+'__baseline',target_law_id=None,
                    target_type='baseline',rationale='Neutral shared bay and source context; no legal verdict')
    for key in ('paired_probe_id','deliberate_differences','probe'):baseline.pop(key,None)
    write(FOLDER/'proposals/cases.json',{'cell_id':'C385967','actor':'motor_vehicle_driver',
        'status':'draft','sweep_specs':[],'cases':[baseline]+proposals})
    write(FOLDER/'execution-manifest.json',{'format':'worker-execution-manifest',
        'assignment_id':FOLDER.name,'runtime_manifest_sha256':sha(ROOT/'runtime/SOURCE-MANIFEST.json'),
        'status':'selected_cpu_prepared','cases':entries})
    print(json.dumps({'cases':len(entries),'manifest_sha256':sha(FOLDER/'execution-manifest.json')},sort_keys=True))


if __name__=='__main__':main()
