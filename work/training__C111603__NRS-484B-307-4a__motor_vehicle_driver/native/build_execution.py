"""Bind selected C111603 CPU evidence to the final delivery manifest."""
import hashlib
import json
import os
from pathlib import Path
import shlex

ROOT=Path(__file__).resolve().parent.parent
SCRATCH=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    preflight_path=ROOT/'selected-preflight-manifest.json'
    preflight=read(preflight_path)
    preflight_sha=sha(preflight_path)
    compatible={r['case_id']:r for r in read(ROOT/'compatibility/index.json')['passed']}
    saved={r['case_id']:r for r in read(ROOT/'recorded-only/index.json')['passed']}
    audits={r['case_id']:r for r in read(ROOT/'delivery-audit/index.json')['cases']}
    entries=[]
    for source in preflight['cases']:
        entry=dict(source)
        case=entry['case_id']
        suffix=case.rsplit('__',1)[-1]
        com=compatible[case]
        rec=saved[case]
        aud=audits[case]
        if sha(ROOT/com['receipt'])!=com['receipt_sha256']:
            raise ValueError('Compatibility receipt hash changed: '+case)
        if read(ROOT/com['receipt'])['construction_sha256']!=entry['construction_sha256']:
            raise ValueError('Compatibility selected another construction: '+case)
        tokens=shlex.split(com['command'])
        attempt=Path(tokens[tokens.index('--output')+1])
        if read(attempt/'candidate-selection.json')['manifest_sha256']!=preflight_sha:
            raise ValueError('Compatibility selected another manifest: '+case)
        if sha(ROOT/rec['proof'])!=rec['proof_sha256'] or read(ROOT/rec['proof'])['manifest_sha256']!=preflight_sha:
            raise ValueError('Recorded-only proof changed: '+case)
        physical=ROOT/'physical'/suffix/'receipt.json'
        entry['compatibility']={'receipt':com['receipt'],'sha256':com['receipt_sha256'],
            'log':com['analysis_log'],'negative_log':com['negative_log']}
        entry['negative']={'log':com['negative_log'],'log_sha256':com['negative_log_sha256']}
        entry['physical_preparation']={'receipt':str(physical.relative_to(ROOT)),'sha256':sha(physical)}
        survey='.runtime-work/original-surveys/'+preflight['assignment_id']+'/'+case+'/context-survey.json'
        entry['native_handoff']={'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST',
            'port_env_var':'CARLA_PORT','survey_env_var':'SCENARIO_CONTEXT_SURVEY',
            'survey_path':survey,'capture_command_prefix':'SCENARIO_CONTEXT_SURVEY='+survey,
            'execute_command_prefix':'SCENARIO_CONTEXT_SURVEY='+survey}
        entry['acquisition']={
            'original_native_signal_and_participants':{'entrypoint':'capture.py',
                'method':'Original Native signal actor and ego, pedestrian and other traffic poses joined to source frame',
                'evidence':['native.jsonl','signal_frames.jsonl','motion_frames.jsonl','intersection-context.json']},
            'four_camera_video':{'entrypoint':'capture.py','method':'Four original synchronized RGB streams and frame map',
                'evidence':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv','video_frames.jsonl']}}
        construction=read(ROOT/entry['construction'])
        for channel in construction['recording_description']['channels']:
            name=channel['name']
            entry['acquisition'][name]={'entrypoint':'capture.py',
                'method':'Original Native source projection; source and independent review retained for '+name,
                'evidence':['native.jsonl','signal_frames.jsonl','motion_frames.jsonl',
                            'video_frames.jsonl','channels/'+name+'.jsonl']}
        proof=read(ROOT/rec['proof'])
        entry['post_capture']={'recorded_only':True,
            'command':'runtime.py process-saved --manifest work/'+preflight['assignment_id']+'/execution-manifest.json --case '+case+' --attempt $ORIGINAL_ATTEMPT --output $DERIVED_OUTPUT --library runtime/library --validator $LEAN_VALIDATOR',
            'feedback_command':'test -f $DERIVED_OUTPUT/v0001/feedback.json && cat $DERIVED_OUTPUT/v0001/feedback.json',
            'test_exit_code':proof['test_exit_code'],'test_log':proof['test_log'],
            'test_log_sha256':proof['test_log_sha256']}
        entry['delivery_acceptance']={'case_id':case,'sets':['full-train'],
            'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
            **{key:aud[key] for key in ('script','script_sha256','command','test_exit_code',
                'test_log','test_log_sha256','negative_command','negative_exit_code',
                'negative_expected_error','negative_log','negative_log_sha256')}}
        entry['preparation_status']='cpu_proven_original_delivery_pending'
        entry['delivery_readiness']='cpu_prepared_original_capture_pending'
        entries.append(entry)
    final={'format':'worker-execution-manifest','assignment_id':preflight['assignment_id'],
           'runtime_manifest_sha256':preflight['runtime_manifest_sha256'],'cases':entries}
    stage=SCRATCH/'c111603-execution-manifest.stage'
    stage.write_text(json.dumps(final,indent=2)+'\n')
    os.replace(stage,ROOT/'execution-manifest.json')
    print(json.dumps({'selected_cases':len(entries),'manifest_sha256':sha(ROOT/'execution-manifest.json')}))

if __name__=='__main__':
    main()
