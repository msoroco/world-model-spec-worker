"""Package exact C229410 sources and original Native CPU drafts."""
import hashlib
import json
from pathlib import Path
from source_channels import SOURCE_NAMES

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
ASSIGNMENT=ROOT.name
CAMERAS=['overview','approach','reference_corner','driver_reference']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries=[]
    for suffix in ('controlled_1','controlled_2'):
        case_id=ASSIGNMENT+'__'+suffix
        description={'channels':[{'name':'parking_geometry','unit':'mixed','sampling_rate_hz':20,
            'method':'original Native full-body corners and speed readback',
            'time_window':'600 frames','reference_frame':'sourced highway and fire-station entrance',
            'uncertainty':'50 ms frame interval; legal distance reference unresolved'}],
            'context_inputs':[{'name':name,'unit':'structured',
                'method':'original hash-bound authority and Native actor source; retain unverified state'}
                for name in SOURCE_NAMES],
            'limitations':['Raw body-edge gap is not a statutory reference-point verdict',
                'Actual station, entrance and pixels require Native and independent review']}
        config={'case_id':case_id,'case_suffix':suffix,'cell_id':'C229410','law_id':'NRS-484B-450-1j',
            'actor':'motor_vehicle_driver','duration_s':30,'rate_hz':20,'cameras':CAMERAS,
            'initial_activity':'parked','exception_context':'none',
            'selected_case_id':case_id,'supported_case_ids':[case_id],'candidate_id':'primary',
            'required_atoms':[],'source_packets':[],'case':{'case_id':case_id},
            'recording_description':description,
            'target':'beyond 20 feet from entrance' if suffix=='controlled_1' else 'within 20 feet from entrance'}
        files=[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
        for name in ('layout.py','runner.py','measure_entrance.py','source_context.py','source_channels.py','finalize.py','tests/test_native.py'):
            files.append({'path':name,'content':(HERE/name).read_text()})
        for name in ('assignment.json','witnesses.json'):
            source=Path('inputs')/ASSIGNMENT/name
            files.append({'path':name,'content':source.read_text()})
        proposal={'case_id':case_id,'cell_id':'C229410','law_id':'NRS-484B-450-1j',
            'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
            'recording_description':description,
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
