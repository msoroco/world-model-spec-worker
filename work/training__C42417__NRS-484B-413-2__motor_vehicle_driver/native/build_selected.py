"""Bind current exact C42417 CPU drafts; incomplete receipts stay explicit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    draft = json.loads((HERE / 'draft-manifest.json').read_text())
    runtime_hash = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    proposals = []
    entries = []
    for suffix, target in (('a', 40), ('b', 20)):
        case = FOLDER.name + '__selected_c8ca9085__condition_' + suffix
        draft_entry = next(item for item in draft['cases'] if item['case_id'] == case)
        construction = json.loads((HERE / draft_entry['construction']).read_text())
        description = construction['recording_description']
        proposal = {'case_id':case,'target_law_id':plan['law_id'],
            'target_type':'delivery','rationale':
                'Isolate the continuous right-indicator distance in the fixed business-district right-turn scene',
            'variable_assignments':{
                'requested_continuous_signal_distance_m':
                    {'kind':'controller','value':target,'unit':'m'},
                'observed_continuous_signal_distance_m':
                    {'kind':'subject_behavior','value':None,'unit':'m'},
                'area_classification':
                    {'kind':'world_setup','value':'business_district','unit':'categorical'}},
            'unresolved_judgment_calls':[
                'Original Native district identity and flashing right-lamp pixels require independent review'],
            'recording_description':description}
        proposals.append(proposal)
        fixtures=[]
        for kind in ('complete_motion','incomplete_motion','missing_evidence'):
            stem=f'native/physical-{suffix}-{kind}'
            command=('.venv-cpu/bin/python '+str((HERE/'prove_physical.py').relative_to(ROOT))+
                ' --source .runtime-work/c42417-selected-'+suffix+'-fixture'+
                ' --kind '+kind+' --output work/'+FOLDER.name+'/'+stem+'.json'+
                ' --scratch .runtime-work/c42417-test-tmp')
            fixtures.append({'kind':kind,'command':command,'exit_code':0,
                'log':stem+'.log','log_sha256':sha(FOLDER/(stem+'.log')),
                'result':stem+'.json','result_sha256':sha(FOLDER/(stem+'.json'))})
        lifecycle_path=HERE/f'physical-{suffix}-lifecycle.log'
        lifecycle_path.write_text('Synthetic fixture lifecycle proof: source fixture completed, video encoders closed, no Native owner acquired, saved finalization started after materialization.\n')
        physical={'format':'c42417-physical-preparation-v1','case_id':case,
            'construction_sha256':draft_entry['construction_sha256'],
            'fixtures':fixtures,'lifecycle':{'events':['capture_finished','encoders_closed',
                'restoration_verified','native_exit','owner_released','saved_processing_started'],
                'exit_code':0,'log':str(lifecycle_path.relative_to(FOLDER)),
                'log_sha256':sha(lifecycle_path),
                'scope':'synthetic CPU lifecycle mock; no original Native session acquired'},
            'scope':'source-shaped CPU outcomes; original Native physical completion unverified'}
        physical_path=HERE/f'physical-{suffix}-receipt.json'
        write(physical_path,physical)
        offline_log=HERE/f'current-condition-{suffix}-primary-offline.log'
        fallback_log=HERE/f'current-condition-{suffix}-fallback1-offline.log'
        alternate=draft_entry['candidates'][0]
        fallback={'id':'fallback1',
            'construction':'native/'+alternate['construction'],
            'construction_sha256':alternate['construction_sha256'],
            'trigger':{'metric':'maximum_original_turn_route_error_m',
                'failure_condition':'original controller route error exceeds 0.35 m before destination road',
                'source':'original Native pose and controller_request.route_error_m'},
            'changed_knobs':['controller_lookahead_base_m'],
            'offline':{'command':'.venv-cpu/bin/python runtime.py offline --manifest work/'+FOLDER.name+
                '/native/draft-manifest.json --case '+case+' --candidate fallback1 --output .runtime-work/c42417-offline-selected2-'+suffix+'-fallback1',
                'exit_code':0,'construction_sha256':alternate['construction_sha256'],
                'log':'native/'+fallback_log.name,'log_sha256':sha(fallback_log),
                'scope':'exact unselected CPU offline; simulation_started=false'},
            'compatibility':{'status':'not_yet_proven'}}
        entry={'case_id':case,'kind':'delivery','id':'primary',
            'construction':'native/'+draft_entry['construction'],
            'construction_sha256':draft_entry['construction_sha256'],
            'candidate_risk':{'status':'physical','reason':
                'Native lane containment and route error must be measured on original poses'},
            'candidates':[fallback],
            'measurement_contract':f'native/selected-{suffix}-measurement-contract.json',
            'measurement_procedure':{'entrypoint':'finalize.py','status':'saved_source_diagnostic'},
            'fixture_recipe':f'work/{FOLDER.name}/native/selected-{suffix}-fixture-recipe.json',
            'physical_preparation':{'receipt':str(physical_path.relative_to(FOLDER)),
                'sha256':sha(physical_path),
                'scope':'synthetic CPU triads; original Native completion unverified'},
            'offline':{'command':'.venv-cpu/bin/python runtime.py offline --manifest work/'+FOLDER.name+
                '/native/draft-manifest.json --case '+case+' --candidate primary --output .runtime-work/c42417-offline-selected2-'+suffix+'-primary',
                'exit_code':0,'construction_sha256':draft_entry['construction_sha256'],
                'log':'native/'+offline_log.name,'log_sha256':sha(offline_log),
                'scope':'exact unselected CPU offline; simulation_started=false'},
            'native_handoff':{'python_env_var':'CARLA_PYTHON',
                'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},
            'compatibility':{'status':'not_yet_proven'},
            'acquisition':{},'negative':{},'delivery_acceptance':{}}
        entries.append(entry)
    write(FOLDER/'proposals/cases.json',{'cell_id':'C42417','actor':'motor_vehicle_driver',
        'status':'draft','sweep_specs':[],'cases':proposals})
    manifest={'format':'worker-execution-manifest','assignment_id':FOLDER.name,
        'runtime_manifest_sha256':runtime_hash,
        'status':'selected_cpu_preparation_incomplete','cases':entries}
    write(FOLDER/'execution-manifest.json',manifest)
    return {'cases':len(entries),'runtime_manifest_sha256':runtime_hash,
            'manifest_sha256':sha(FOLDER/'execution-manifest.json'),
            'status':manifest['status']}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
