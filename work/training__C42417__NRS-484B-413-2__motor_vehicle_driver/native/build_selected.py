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


def compatibility(suffix, candidate):
    stem = f'selected-{suffix}-{candidate}'
    receipt = HERE / f'{stem}-compatibility.json'
    analysis = HERE / f'{stem}-analysis.log'
    negative = HERE / f'{stem}-negative.log'
    if not all(path.is_file() for path in (receipt, analysis, negative)):
        return {'status': 'not_yet_proven'}
    return {'receipt': f'native/{receipt.name}', 'sha256': sha(receipt),
            'log': f'native/{analysis.name}',
            'negative_log': f'native/{negative.name}'}


def delivery(case, suffix):
    script=HERE/'delivery_audit.py'
    positive=HERE/f'delivery-{suffix}-positive.log'
    negative=HERE/f'delivery-{suffix}-negative.log'
    if not all(path.is_file() for path in (script,positive,negative)):
        return {}
    prefix=f'.venv-cpu/bin/python work/{FOLDER.name}/native/delivery_audit.py --case {case}'
    return {'case_id':case,'sets':['demo-train','full-train'],
        'checks':['native_source','all_participants','time_join','full_video_decode',
                  'actual_pixels','physical_completion'],
        'script':'native/delivery_audit.py','script_sha256':sha(script),
        'command':prefix+' --selftest','test_exit_code':0,
        'test_log':f'native/{positive.name}','test_log_sha256':sha(positive),
        'negative_command':prefix+' --negative-selftest',
        'negative_exit_code':1,
        'negative_expected_error':'Reviewed pixel box exceeds source video',
        'negative_log':f'native/{negative.name}',
        'negative_log_sha256':sha(negative),
        'scope':'synthetic CPU mechanics; original source review required'}


def post_capture(case, suffix):
    log = HERE / f'selected-{suffix}-saved-test.log'
    receipt = HERE / f'selected-{suffix}-saved-receipt.json'
    feedback = HERE / f'selected-{suffix}-saved-negative-feedback.json'
    if not all(path.is_file() and path.stat().st_size for path in (log, receipt, feedback)):
        return {}
    if not (json.loads(receipt.read_text()).get('recorded_only') is True and
            json.loads(feedback.read_text()).get('recorded_only') is True):
        raise ValueError('Saved processing was not recorded-only')
    command = ('.venv-cpu/bin/python runtime.py process-saved --manifest '
        f'work/{FOLDER.name}/execution-manifest.json --case {case} '
        '--attempt $ATTEMPT --output $OUTPUT --library runtime/library '
        '--validator $VALIDATOR')
    return {'recorded_only':True,'command':command,
        'feedback_command':f'cat $OUTPUT/v0001/feedback.json # {case}',
        'test_exit_code':0,'test_log':f'native/{log.name}',
        'test_log_sha256':sha(log),'positive_processing_receipt':f'native/{receipt.name}',
        'positive_processing_sha256':sha(receipt),
        'missing_source_feedback':f'native/{feedback.name}',
        'missing_source_feedback_sha256':sha(feedback),
        'scope':'source-shaped synthetic saved positive and missing-source negative; original physical recording unverified'}


def build():
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    draft = json.loads((HERE / 'draft-manifest.json').read_text())
    runtime_hash = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    proposals = []
    entries = []
    for suffix, target in (('a', 40), ('b', 20), ('c', 30.48)):
        case = FOLDER.name + '__selected_c8ca9085__condition_' + suffix
        draft_entry = next(item for item in draft['cases'] if item['case_id'] == case)
        construction = json.loads((HERE / draft_entry['construction']).read_text())
        description = construction['recording_description']
        proposal = {'case_id':case,'target_law_id':plan['law_id'],
            'target_type':'boundary_probe','rationale':
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
            'recording_description':description,
            'paired_probe_id':plan['law_id']+'@motor_vehicle_driver:business_signal_distance',
            'deliberate_differences':['requested_continuous_signal_distance_m'],
            'probe':{'primary_variable':'observed_continuous_signal_distance_m',
                'comparison_or_standard':'NRS 484B.413(2) business-district 100 ft clause',
                'target_value_or_branch':target,'test_value':target,
                'operator':'>=','unit':'m',
                'threshold_ref':'timing.numeric_conditions[0]'},
            'epsilon_used':{'value':10.48,'unit':'m',
                'purpose':'source-grounded below/at/above probe spacing'}}
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
            'compatibility':compatibility(suffix,'fallback1')}
        config=json.loads(next(file['content'] for file in construction['files']
                               if file['path']=='config.json'))
        required=set(config['required_atoms']) | {channel['name'] for channel in description['channels']}
        acquisition={atom:{'entrypoint':'capture.py' if atom in config['required_atoms'] else 'finalize.py',
            'method':'source-bound Native sample or deterministic saved-source measurement',
            'evidence':'capture/native_samples.jsonl and analysis-report.json'} for atom in sorted(required)}
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
            'compatibility':compatibility(suffix,'primary'),
            'acquisition':acquisition,
            'negative':{'log':f'native/selected-{suffix}-primary-negative.log'},
            'delivery_acceptance':delivery(case,suffix),
            'post_capture':post_capture(case,suffix)}
        entries.append(entry)
    baseline=dict(proposals[0])
    baseline.update(case_id=FOLDER.name+'__baseline', target_law_id=None,
                    target_type='baseline', rationale='Shared source-measurement baseline with no legal verdict')
    for key in ('paired_probe_id','deliberate_differences','probe'):
        baseline.pop(key,None)
    write(FOLDER/'proposals/cases.json',{'cell_id':'C42417','actor':'motor_vehicle_driver',
        'status':'draft','sweep_specs':[],'cases':[baseline]+proposals})
    manifest={'format':'worker-execution-manifest','assignment_id':FOLDER.name,
        'runtime_manifest_sha256':runtime_hash,
        'status':'selected_cpu_prepared','cases':entries}
    write(FOLDER/'execution-manifest.json',manifest)
    return {'cases':len(entries),'runtime_manifest_sha256':runtime_hash,
            'manifest_sha256':sha(FOLDER/'execution-manifest.json'),
            'status':manifest['status']}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
