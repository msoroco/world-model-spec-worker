"""Map each exact C132497 statutory topic to its planned synthetic evidence."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
sys.path.insert(0,str(HERE))
import measure_saved

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build():
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    source=json.loads(assignment.read_text());planned=json.loads(plan.read_text())
    if source['law_record']['text']!=planned['source_law_text']:
        raise ValueError('C132497 exact law differs')
    measured={w:measure_saved.measure(CASE/'offline'/'bundles'/w/'primary')
        for w in ('reference','contrast')}
    topics=[]
    for disposition in planned['requirement_dispositions']:
        if disposition['requirement'] not in ('text-0','text-1','text-2'):
            raise ValueError('C132497 topic differs')
        topics.append({'topic':disposition['requirement'],
            'case_ids':disposition['case_ids'],
            'source_assignment_sha256':sha(assignment),
            'case_plan_sha256':sha(plan),
            'evidence_kind':'synthetic_cpu_request_and_saved_measurement',
            'original_right_turn_observed':False,
            'physical_roundabout_verified':False,'legal_verdict':None,
            'status':'pending_original_evidence'})
    result={'format':'c132497-statutory-review-v1','law_id':'LVMC-11-43-010-C2',
        'exact_law_text':source['law_record']['text'],
        'topics':topics,'synthetic_case_measurements':{
            w:{'right_lane_used':m['right_lane_used'],
                'phase_frames':m['phase_frames'],
                'source_hashes':m['source_hashes']}
            for w,m in measured.items()},
        'original_native_observed':False,'legal_verdict':None,
        'delivery_ready':False}
    (CASE/'statutory-review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps({'topics':len(build()['topics'])}))
