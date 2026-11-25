"""Bind selected parked-departure CPU diagnostics to exact source contracts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def build():
    draft=json.loads((HERE/'draft-departure-manifest.json').read_text())
    selected=[]
    for item in draft['cases']:
        case=item['case_id']
        suffix=case.rsplit('__',1)[-1]
        construction=json.loads((HERE/item['construction']).read_text())
        config=json.loads(next(file['content'] for file in construction['files']
                               if file['path']=='config.json'))
        contract={'format':'worker-measurement-contract','case_id':case,
            'requirements':[{'disposition_index':0,'requirement':'NRS-484B-410',
                'source':'NRS 484B.410','output_key':'departure_observation',
                'method':'departure_observation','value_type':'object','kind':'measured',
                'inputs':['departure-trace.jsonl','video_frames.jsonl',
                          'departure-context.json','road.xodr']}],
            'negative':{'remove':['departure-context.json'],
                        'error_contains':'Missing required source: departure-context.json'}}
        write(HERE/('measurement-'+suffix+'.json'),contract)
        item.update(measurement_contract='measurement-'+suffix+'.json',
            measurement_procedure={'entrypoint':'finalize.py',
                                   'output_schema':'c227853-departure-analysis-v1'},
            fixture_recipe='work/'+ASSIGNMENT+'/selected-recipe-'+suffix+'.json',
            native_handoff={'python_env_var':'CARLA_PYTHON',
                            'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},
            acquisition={'participant_footprints':{
                'entrypoint':'runner.py','method':'original Native actor boxes and same-tick four-camera frame join',
                'evidence':'departure-trace.jsonl, video_frames.jsonl and original cameras'},
                'participant_velocity':{
                'entrypoint':'runner.py','method':'original Native actor velocity readback',
                'evidence':'departure-trace.jsonl and video_frames.jsonl'}})
        physical=HERE/'physical-proof'/suffix/'proof.json'
        if physical.is_file():
            proof=json.loads(physical.read_text())
            if proof.get('construction_sha256')!=item['construction_sha256']:
                raise ValueError('Stale physical proof: '+suffix)
            item['physical_preparation']={'receipt':str(physical.relative_to(HERE)),
                                          'sha256':sha(physical)}
        audit=HERE/'delivery_audit.py'
        positive='delivery-proofs/'+suffix+'-positive.log'
        negative='delivery-proofs/'+suffix+'-negative.log'
        if audit.is_file() and (HERE/positive).is_file() and (HERE/negative).is_file():
            command=str(ROOT/'.venv-cpu/bin/python')+' '+str(audit)+' --case '+case+' --self-test'
            item['delivery_acceptance']={'case_id':case,'sets':['full-train'],
                'checks':['native_source','all_participants','time_join',
                          'full_video_decode','actual_pixels','physical_completion'],
                'script':'delivery_audit.py','script_sha256':sha(audit),
                'negative_expected_error':'Missing original source: exact original Native result',
                'command':command,'test_exit_code':0,'test_log':positive,
                'test_log_sha256':sha(HERE/positive),
                'negative_command':command+' --negative','negative_exit_code':1,
                'negative_log':negative,'negative_log_sha256':sha(HERE/negative)}
        for candidate in (['primary']+item['candidates']):
            ident=candidate if isinstance(candidate,str) else candidate['id']
            candidate_entry=item if ident=='primary' else candidate
            prefix=suffix+'-'+ident
            offline_log=prefix+'-offline.log'
            compat='compatibility/'+prefix+'-compatibility.json'
            compat_log='compatibility/'+prefix+'-compatibility-analysis.log'
            negative='compatibility/'+prefix+'-negative-analysis.log'
            if all((HERE/path).is_file() for path in
                   (offline_log,compat,compat_log,negative)):
                receipt=json.loads((HERE/compat).read_text())
                if receipt.get('construction_sha256')==candidate_entry['construction_sha256']:
                    candidate_entry['offline']={'case_id':case,'candidate_id':ident,
                    'construction_sha256':candidate_entry['construction_sha256'],
                    'command':'.venv-cpu/bin/python runtime.py offline --manifest work/'+
                        ASSIGNMENT+'/execution-manifest.json --case '+case+
                        ' --candidate '+ident+' --output .runtime-work/c227853-offline-'+prefix,
                    'exit_code':0,'log':offline_log,'log_sha256':sha(HERE/offline_log)}
                    candidate_entry['compatibility']={'receipt':compat,'sha256':sha(HERE/compat),
                        'log':compat_log,'negative_log':negative}
                    if ident=='primary':
                        item['negative']={'log':negative}
            saved_log='saved-'+prefix+'.log'
            saved_receipt='saved-'+prefix+'-processing.json'
            if ident=='primary' and (HERE/saved_log).is_file() and (HERE/saved_receipt).is_file():
                saved=json.loads((HERE/saved_receipt).read_text())
                if (saved.get('case_id')==case and saved.get('passed') is True and
                        saved.get('analysis_revision',{}).get('construction_sha256')==
                        item['construction_sha256']):
                    item['post_capture']={'recorded_only':True,
                    'command':'.venv-cpu/bin/python runtime.py process-saved --manifest work/'+
                        ASSIGNMENT+'/execution-manifest.json --case '+case+
                        ' --attempt $ATTEMPT --output $OUTPUT --library runtime/library'+
                        ' --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT',
                    'feedback_command':'cat $OUTPUT/versions/*/feedback.json',
                    'test_exit_code':0,'test_log':saved_log,
                    'test_log_sha256':sha(HERE/saved_log),
                    'processing_receipt':saved_receipt,
                    'processing_sha256':sha(HERE/saved_receipt)}
        status=config['requested_initial_status']
        permitted=config['requested_parking_permitted']
        pair_number=(int(suffix.rsplit('_',1)[-1])+1)//2
        selected.append({'case_id':case,'target_law_id':'NRS-484B-410',
            'target_type':'judgment_sweep',
            'rationale':'Source-shaped '+status+' highway departure contrast; parking permitted='+str(permitted),
            'paired_probe_id':ASSIGNMENT+'__comparison_'+str(pair_number),
            'deliberate_differences':['initial approaching traffic position'],
            'probe':{'primary_variable':'initial_approaching_traffic_position',
                     'comparison_or_standard':'paired clearance and conflict contrast',
                     'target_value_or_branch':suffix},
            'variable_assignments':{'initial_approaching_traffic_position':{
                'kind':'controller','value':-55 if int(suffix[-1])%2==0 else 15},
                'initial_status':{'kind':'authority_source','value':status},
                'parking_permitted':{'kind':'authority_source','value':permitted}},
            'recording_description':config['recording_description'],
            'unresolved_judgment_calls':['with safety','Nevada public highway',
                                         'parking permission and statutory exception']})
    write(HERE/'proposals/cases.json',{'cell_id':'C227853',
        'actor':'motor_vehicle_driver','status':'draft','cases':selected})
    draft['format']='worker-execution-manifest'
    write(HERE/'execution-manifest.json',draft)
    return {'selected_case_ids':[entry['case_id'] for entry in draft['cases']],
            'execution_manifest_sha256':sha(HERE/'execution-manifest.json')}


if __name__=='__main__':
    print(json.dumps(build()))
