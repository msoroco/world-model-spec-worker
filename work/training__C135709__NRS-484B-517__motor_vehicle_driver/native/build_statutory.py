"""Map exact C135709 statute and selected branch to measured synthetic witnesses."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build():
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    source=json.loads(assignment.read_text());cases=json.loads(plan.read_text())
    review={'format':'c135709-statutory-review-v1',
        'assignment_id':CASE.name,'assignment_sha256':sha(assignment),
        'case_plan_sha256':sha(plan),'law_id':'NRS-484B-517',
        'exact_law_text':source['law_record']['text'],
        'selected_scope':'Non-taxicab parking in a taxicab stand',
        'source_topics':[{'requirement':d['requirement'],'status':'pending_original_review',
            'case_ids':d['case_ids']} for d in cases['requirement_dispositions']],
        'synthetic_case_measurements':[],
        'required_original_review':[
            'official stand designation and appropriately signed spatial applicability',
            'subject actual non-taxicab use and destination parking purpose',
            'observed parked occupancy, duration and body position',
            'actual passenger loading/unloading and expeditious duration',
            'taxicab waiting or about to enter and interference during occupancy',
            'prohibited-stopping exclusions and accepted equivalence review'],
        'exception_adjudicated':False,'legal_verdict':None,
        'original_native_observed':False,'delivery_ready':False}
    for witness in ('reference','contrast'):
        bundle=CASE/'offline/bundles'/witness/'primary'
        measurement=__import__('subprocess').run([
            __import__('sys').executable,str(bundle/'measure_saved.py'),str(bundle)],
            capture_output=True,text=True,check=True,timeout=20)
        result=json.loads(measurement.stdout)
        review['synthetic_case_measurements'].append({
            'case_id':CASE.name+'__'+witness,
            'saved_source_hashes':result['source_hashes'],
            'stationary_frames':result['stationary_frames'],
            'full_body_stand_occupied_frames':result['full_body_stand_occupied_frames'],
            'source_kind':'synthetic_cpu','legal_verdict':None})
    path=CASE/'statutory-review.json'
    path.write_text(json.dumps(review,indent=2)+'\n')
    return review

if __name__=='__main__':print(json.dumps({'topics':len(build()['source_topics'])}))
