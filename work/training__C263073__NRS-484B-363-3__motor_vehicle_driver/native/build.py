"""Package exact C263073 sources and original Native CPU drafts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;ASSIGNMENT=ROOT.name
CAMERAS=['overview','zone_entry','turn_side','child_area']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries=[]
    for suffix in ('controlled_1','controlled_2'):
        case_id=ASSIGNMENT+'__'+suffix
        config={'case_id':case_id,'case_suffix':suffix,'cell_id':'C263073','law_id':'NRS-484B-363-3',
            'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'cameras':CAMERAS,
            'target':'defer U-turn and continue' if suffix=='controlled_1' else 'kinematic U-turn within authored zone'}
        files=[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
        for name in ('layout.py','runner.py','measure_turn.py','review_context.py','tests/test_native.py','tests/test_review_context.py'):
            files.append({'path':name,'content':(HERE/name).read_text()})
        for name in ('assignment.json','witnesses.json'):
            source=Path('inputs')/ASSIGNMENT/name;files.append({'path':name,'content':source.read_text()})
        proposal={'case_id':case_id,'cell_id':'C263073','law_id':'NRS-484B-363-3',
            'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
            'recording_description':{'rate_hz':20,'duration_s':30,'cameras_required':CAMERAS,
                'required_original_sources':['Native vehicle trajectory and heading','school-zone designation and boundary',
                    'child identities and locations','session, operation, class-hour and civil-time records',
                    'beacon and sign-state record','all five exception dispositions','four synchronized original cameras'],
                'limitations':['Kinematic path is a CPU draft, not a physically accepted U-turn',
                    'Generic walker blueprint does not establish child age or legal presence',
                    'Diagnostic zone outline is not official designation',
                    'No legal heading threshold or presence radius is adopted']},
            'status':'selected_native_cpu_draft_not_delivery_prepared',
            'static_checks':['authored two-way OpenDRIVE road','600-frame heading reversal path',
                'one separate person position','four synchronized FFV1 cameras',
                'source-bound raw trajectory measurement']}
        target=HERE/'bundles'/suffix/'construction.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(proposal,indent=2)+'\n')
        entries.append({'case_id':case_id,'kind':'delivery','construction':str(target.relative_to(ROOT)),
            'construction_sha256':sha(target),
            'candidate_risk':{'status':'physical','reason':'Kinematic path, official school zone and child presence unverified'},
            'candidates':[],'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':ASSIGNMENT,
        'status':'partial','cases':entries,'physical_acceptance_claimed':False}
    (ROOT/'draft-native-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'construction_sha256':[x['construction_sha256'] for x in entries]}))


if __name__=='__main__':build()
