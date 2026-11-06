"""Materialize eight exact, unselected C111294 bicycle/motorist CPU drafts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
NATIVE=HERE/'native'
NAMES=('primary','fallback1','fallback2','fallback3')
FILES=('runner.py','runner_capture.py','geometry.py','engineering.py','cameras.py','measure.py','trigger_measure.py','finalize.py')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    batch=json.loads((ROOT/'batch.json').read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    assert [row['case_id'].split('__')[-1] for row in plan['cases']]==['witness_1','witness_2']
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
        'assignment_id':HERE.name,'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
        'status':'draft_not_selected','cases':[]}
    common=[{'path':name,'content':(NATIVE/name).read_text()} for name in FILES]
    common.append({'path':'tests/test_native.py','content':(NATIVE/'test_native.py').read_text()})
    for case in plan['cases']:
        case_id=case['case_id'];suffix=case_id.split('__')[-1]
        contract=NATIVE/('measurement-contract-'+suffix+'.json')
        if json.loads(contract.read_text())['case_id']!=case_id:raise ValueError('Case contract differs')
        entry={'case_id':case_id,'kind':'draft_not_selected',
            'measurement_contract':str(contract.relative_to(HERE)),
            'candidate_risk':{'status':'physical','reason':'Bicycle blueprint, motorist reaction, body clearance and camera coverage unobserved'},
            'measurement_procedure':{'entrypoint':'finalize.py','output_schema':'c111294-saved-analysis-v1'},
            'candidates':[]}
        for candidate in NAMES:
            from importlib.util import spec_from_file_location,module_from_spec
            spec=spec_from_file_location('engineering',NATIVE/'engineering.py')
            engineering=module_from_spec(spec);spec.loader.exec_module(engineering)
            params=engineering.parameters(suffix,candidate)
            config={'case_id':case_id,'selected_case_id':case_id,'supported_case_ids':[case_id],
                'case_suffix':suffix,'candidate_id':candidate,'cell_id':'C111294',
                'law_id':'NRS-484B-270-7a','actor':'cycle_or_scooter_operator',
                'rate_hz':20,'duration_s':24,'required_atoms':['st.intersection','kin.position'],
                'source_packets':[],
                'case':{'case_id':case_id},'knobs':params['knobs'],
                'recording_description':{'channels':[
                    {'name':name,'unit':'structured','sampling_rate_hz':20,
                     'method':'original Native actor/camera source; synthetic CPU fixture is diagnostic',
                     'time_window':'entire 24 s / 480-frame attempt',
                     'reference_frame':'surveyed Native map and original frame identity',
                     'uncertainty':'50 ms sampling; human propulsion, intent and pixels require physical review'}
                    for name in ('bicycle_body_pose','motorist_body_pose','motorist_brake','camera_frame_join')],
                    'context_inputs':[],
                    'limitations':['Synthetic CPU fixture cannot establish physical class, intent or original pixels']},
                'status':'unselected_native_draft'}
            files=common+[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
            construction={'case_id':case_id,'law_id':'NRS-484B-270-7a','cell_id':'C111294',
                'actor':'cycle_or_scooter_operator','entrypoint':'runner.py','files':files,
                'recording_description':config['recording_description'],
                'measurement_plan':{'method':'Original frame-joined bicycle and motorist bodies, braking and clearance; no intent inference',
                                    'status':'source_bound_cpu_draft'},
                'static_checks':['two through-connector OpenDRIVE map','two actor class and body sources',
                                 'four candidate knob sets and source-bound trigger tests'],
                'termination_rules':['480 original 20 Hz frames','retain failed capture and restoration report'],
                'mechanisms':['bicycle through route','separate motorist through route',
                              'observed Native actor body/pose samples','proposed four original camera views'],
                'status':'unselected_cpu_draft'}
            rel=f'draft-candidates/{suffix}/{candidate}/construction.json'
            path=HERE/rel;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(construction,indent=2)+'\n')
            reference={'id':candidate,'construction':rel,'construction_sha256':sha(path)}
            if candidate=='primary':entry.update(reference)
            else:
                trigger=engineering.TRIGGERS[candidate]
                reference.update(trigger={'source':trigger['source'],'metric':trigger['metric'],
                    'failure_condition':f"{trigger['metric']} {trigger['op']} {trigger['threshold']}"},
                    changed_knobs=[key for key in engineering.CHANGES[candidate]])
                entry['candidates'].append(reference)
        manifest['cases'].append(entry)
    (HERE/'draft-execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return {'cases':len(manifest['cases']),'candidates':sum(1+len(x['candidates']) for x in manifest['cases']),
            'status':manifest['status']}

if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
