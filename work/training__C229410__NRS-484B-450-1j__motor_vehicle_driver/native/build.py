"""Package exact C229410 sources and original Native CPU drafts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
ASSIGNMENT=ROOT.name
CAMERAS=['overview','entrance','near_side','approach']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries=[]
    for suffix in ('controlled_1','controlled_2'):
        case_id=ASSIGNMENT+'__'+suffix
        config={'case_id':case_id,'case_suffix':suffix,'cell_id':'C229410','law_id':'NRS-484B-450-1j',
            'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'cameras':CAMERAS,
            'target':'beyond 20 feet from entrance' if suffix=='controlled_1' else 'within 20 feet from entrance'}
        files=[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
        for name in ('layout.py','runner.py','measure_entrance.py','tests/test_native.py'):
            files.append({'path':name,'content':(HERE/name).read_text()})
        for name in ('assignment.json','witnesses.json'):
            source=Path('inputs')/ASSIGNMENT/name
            files.append({'path':name,'content':source.read_text()})
        proposal={'case_id':case_id,'cell_id':'C229410','law_id':'NRS-484B-450-1j',
            'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
            'recording_description':{'rate_hz':20,'duration_s':30,'cameras_required':CAMERAS,
                'required_original_sources':['Native vehicle full-body motion','fire-station identity',
                    'driveway entrance extent and highway side','parking activity and exceptions',
                    'four synchronized original cameras'],
                'limitations':['Diagnostic driveway outline does not establish fire-station identity',
                    'Raw geometry does not adopt statutory reference point or decide 20-foot clause',
                    'Opposite-side 75-foot clause is not covered by selected pair']},
            'status':'selected_native_cpu_draft_not_delivery_prepared',
            'static_checks':['authored OpenDRIVE highway','diagnostic driveway outline',
                '600 original Native frames','four synchronized FFV1 cameras',
                'source-bound raw vehicle-to-entrance measurement']}
        target=HERE/'bundles'/suffix/'construction.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(proposal,indent=2)+'\n')
        entries.append({'case_id':case_id,'kind':'delivery','construction':str(target.relative_to(ROOT)),
            'construction_sha256':sha(target),
            'candidate_risk':{'status':'physical',
                'reason':'Fire-station identity, driveway and parking event are physically unverified'},
            'candidates':[],'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':ASSIGNMENT,
        'status':'partial','cases':entries,'physical_acceptance_claimed':False}
    (ROOT/'draft-native-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'construction_sha256':[x['construction_sha256'] for x in entries]}))


if __name__=='__main__':build()
