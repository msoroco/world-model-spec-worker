"""Package exact C245532 sources and original Native CPU drafts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;ASSIGNMENT=ROOT.name
CAMERAS=['overview','separator_side','entrance_view','traffic_view']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries=[]
    for suffix in ('controlled_1','controlled_2'):
        case_id=ASSIGNMENT+'__'+suffix
        config={'case_id':case_id,'case_suffix':suffix,'cell_id':'C245532','law_id':'NRS-484B-587-2b',
            'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'cameras':CAMERAS,
            'target':'remain on entrance-lane side' if suffix=='controlled_1' else 'move across separator into traffic lane'}
        files=[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
        for name in ('layout.py','runner.py','measure_separator.py','tests/test_native.py'):
            files.append({'path':name,'content':(HERE/name).read_text()})
        for name in ('assignment.json','witnesses.json'):
            source=Path('inputs')/ASSIGNMENT/name;files.append({'path':name,'content':source.read_text()})
        proposal={'case_id':case_id,'cell_id':'C245532','law_id':'NRS-484B-587-2b',
            'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
            'recording_description':{'rate_hz':20,'duration_s':30,'cameras_required':CAMERAS,
                'required_original_sources':['Native lane IDs and body motion','public-highway and controlled-access status',
                    'official entrance-lane and traffic-lane functions','solid white separator geometry',
                    'emergency necessity and subsection 3 conditions','four synchronized original cameras'],
                'limitations':['OpenDRIVE motorway label alone does not prove legal controlled-access status',
                    'Shoulder authorization is not treated as permission to cross this separator',
                    'Body straddling and center transition are raw facts, not a statutory cutoff']},
            'status':'selected_native_cpu_draft_not_delivery_prepared',
            'static_checks':['authored same-direction two-lane OpenDRIVE','solid white separator',
                '600 original Native frames','four synchronized FFV1 cameras',
                'source-bound raw body and lane-transition measurement']}
        target=HERE/'bundles'/suffix/'construction.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(proposal,indent=2)+'\n')
        entries.append({'case_id':case_id,'kind':'delivery','construction':str(target.relative_to(ROOT)),
            'construction_sha256':sha(target),
            'candidate_risk':{'status':'physical','reason':'Legal access status, official lane functions and crossing path unverified'},
            'candidates':[],'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':ASSIGNMENT,
        'status':'partial','cases':entries,'physical_acceptance_claimed':False}
    (ROOT/'draft-native-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'construction_sha256':[x['construction_sha256'] for x in entries]}))


if __name__=='__main__':build()
