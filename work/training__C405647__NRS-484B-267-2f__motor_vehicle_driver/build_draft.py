"""Build exact selected-case CPU drafts bound to Native source code."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
CAMERAS=('overview','ego_front','emergency_side','rear')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')

def main():
    entries=[]
    for suffix in ('controlled_1','controlled_2'):
        case=AID+'__'+suffix
        cfg={'assignment_id':AID,'case_id':case,'selected_case_id':case,'case_suffix':suffix,
             'candidate_id':'primary','law_id':'NRS-484B-267-2f','cell_id':'C405647',
             'actor':'motor_vehicle_driver','rate_hz':20,'duration_s':30,'frames':600,
             'cameras':[{'name':x,'width':1280,'height':720,'fps':20} for x in CAMERAS],
             'requested_initial_subject_speed_mps':3,'requested_subsequent_emergency_speed_mps':2,
             'requested_subsequent_subject_speed_mps':1 if suffix=='controlled_1' else 3,
             'physical_acceptance_claimed':False,'required_atoms':[],'source_packets':[],
             'recording_description':'Two distinct opposite-direction vehicles; original 600-frame pose/velocity/light-state trace, four cameras, reviewed authorization/equipment/officer sources; controlled speed response is a proxy, not a resolved subsection 1 duty'}
        files=[{'path':n,'content':(HERE/'native'/n).read_text()} for n in ('runner.py','measure_approach.py','tests/test_native.py')]
        files.append({'path':'config.json','content':json.dumps(cfg,indent=2)+'\n'})
        construction={'format':'worker-construction','assignment_id':AID,'case_id':case,
                      'law_id':'NRS-484B-267-2f','cell_id':'C405647','actor':'motor_vehicle_driver',
                      'entrypoint':'runner.py','recording_description':cfg['recording_description'],
                      'measurement_plan':{'entrypoint':'measure_approach.py','sources':['video_frames.jsonl','vehicle_poses.jsonl','emergency_context.json'],
                                          'subsection_1_duty_resolved':False,'legal_result':None},'files':files}
        p=HERE/'draft-approach'/suffix/'primary'/'construction.json';write(p,construction)
        entries.append({'case_id':case,'kind':'selected_cpu_draft_not_delivery_ready',
                        'construction':str(p.relative_to(HERE)),'construction_sha256':sha(p),
                        'candidate_risk':{'status':'physical','reason':'Native route, vehicle authorization, qualifying lights and actual response remain unverified'},
                        'candidates':[],'delivery_readiness':'incomplete'})
    manifest={'format':'worker-selected-cpu-draft-manifest-v1','assignment_id':AID,'status':'partial','cases':entries}
    write(HERE/'draft-approach-manifest.json',manifest)
    print(json.dumps({'case_hashes':{e['case_id']:e['construction_sha256'] for e in entries},
                      'manifest_sha256':sha(HERE/'draft-approach-manifest.json')},sort_keys=True))
if __name__=='__main__':main()
