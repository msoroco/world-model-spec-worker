"""Build two source-preserving Native controlled primaries for emergency travel."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
CAMERAS=('overview','approach','side','rear')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def main():
    entries=[]
    for suffix,gap in (('controlled_1',-20),('controlled_2',-20)):
        case=AID+'__'+suffix
        cfg={'assignment_id':AID,'case_id':case,'selected_case_id':case,
            'case_suffix':suffix,'candidate_id':'primary','law_id':'NRS-484B-267-2d',
            'cell_id':'C404492','actor':'motor_vehicle_driver','frames':600,
            'rate_hz':20,'duration_s':30,'engineering_initial_ego_gap_m':gap,
            'cameras':[{'name':n,'width':1280,'height':720} for n in CAMERAS],
            'physical_acceptance_claimed':False,'required_atoms':[],'source_packets':[],
            'recording_description':'Two distinct adjacent-lane Native vehicles, emergency flashing-light phase, 600 original position/heading/velocity/extent frames and four synchronized cameras; independent authorization, equipment and officer-direction review required'}
        files=[{'path':name,'content':(HERE/'native'/name).read_text()} for name in ('runner.py','tests/test_native.py')]
        files.append({'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'})
        files.append({'path':'measure_emergency.py','content':(HERE/'measure_emergency.py').read_text()})
        construction={'format':'worker-construction','assignment_id':AID,'case_id':case,
            'law_id':'NRS-484B-267-2d','cell_id':'C404492','actor':'motor_vehicle_driver',
            'entrypoint':'runner.py','recording_description':cfg['recording_description'],
            'measurement_plan':{'entrypoint':'measure_emergency.py','sources':[
                'video_frames.jsonl','vehicle_poses.jsonl','emergency_context.json'],
                'same_direction_cutoff':None,'abreast_cutoff':None,'legal_result':None},
            'files':files}
        path=HERE/'draft-emergency'/suffix/'primary'/'construction.json';write(path,construction)
        entries.append({'case_id':case,'kind':'selected_cpu_draft_not_delivery_ready',
            'construction':str(path.relative_to(HERE)),'construction_sha256':sha(path),
            'candidate_risk':{'status':'physical','reason':'Authorization, qualifying lamp equipment, actual flash pixels and original same-direction Native travel require review'},
            'candidates':[],'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':AID,
        'status':'partial','cases':entries}
    write(HERE/'draft-emergency-manifest.json',manifest)
    print(json.dumps({'case_hashes':{e['case_id']:e['construction_sha256'] for e in entries},
                      'manifest_sha256':sha(HERE/'draft-emergency-manifest.json')},sort_keys=True))


if __name__=='__main__':main()
