"""Materialize two exact CPU construction drafts from one straight-arrow runner."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CASE_IDS=[ROOT.name+'__clear_straight',ROOT.name+'__yield_straight']


def build(case_id,occupancy):
    proposals=json.loads((ROOT/'proposals/cases.json').read_text())
    proposed=next(case for case in proposals['cases'] if case['case_id']==case_id)
    scene=json.loads((ROOT/'scene.json').read_text())
    scene['case_id']=case_id
    scene['participant_occupancy_setup']=occupancy
    config={'assignment_id':ROOT.name,'selected_case_id':case_id,'supported_case_ids':CASE_IDS,
            'law_id':'NRS-484B-307-5a','cell_id':'C111125','actor':'motor_vehicle_driver',
            'rate_hz':20,'duration_s':30,'required_atoms':[],'source_packets':[],
            'case':{'case_id':case_id,'participant_occupancy_setup':occupancy,
                    'recording_description':proposed['recording_description']},
            'physical_completion':{'criterion':'intersection_clearance',
                                   'motion_source':'ego-body-history.jsonl',
                                   'body_key':'body_vertices_m','exit_axis':0,'exit_sign':1,
                                   'intersection_polygon_xy_m':[[-5,-5],[8,-5],[8,5],[-5,5]],
                                   'minimum_progress_m':5,'minimum_samples':2}}
    files=[]
    for name in ('runner.py','analysis.py','tests/test_runner.py','tests/test_analysis.py'):
        files.append({'path':name,'content':(ROOT/name).read_text()})
    files.append({'path':'scene.json','content':json.dumps(scene,indent=2)+'\n'})
    files.append({'path':'config.json','content':json.dumps(config,indent=2,ensure_ascii=False)+'\n'})
    construction={'law_id':'NRS-484B-307-5a','cell_id':'C111125','actor':'motor_vehicle_driver',
                  'case_id':case_id,'entrypoint':'runner.py','files':files,
                  'recording_description':proposed['recording_description'],
                  'mechanisms':['exact facing-arrow source guard','straight-only yield controller','source-hashed saved analysis'],
                  'measurement_plan':{'signal_and_yield':'Original signal, ego and participant frame joins; legal predicate unresolved'},
                  'static_checks':['straight route crosses stop line and clears intersection','sole-arrow guard rejects generic green'],
                  'termination_rules':['stop after intersection clearance or physical failure']}
    return construction,scene,config


def main():
    manifest={'format':'worker-execution-manifest','assignment_id':ROOT.name,'cases':[]}
    for index,(case_id,occupancy) in enumerate(zip(CASE_IDS,('clear','lawfully_present'))):
        construction,scene,config=build(case_id,occupancy)
        path=ROOT/'construction.json' if index==0 else ROOT/'cases/yield/construction.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(construction,indent=2,ensure_ascii=False)+'\n')
        if index==0:
            (ROOT/'scene.json').write_text(json.dumps(scene,indent=2)+'\n')
            (ROOT/'config.json').write_text(json.dumps(config,indent=2,ensure_ascii=False)+'\n')
        manifest['cases'].append({'case_id':case_id,'kind':'delivery',
             'construction':str(path.relative_to(ROOT)),
             'construction_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
             'candidate_risk':{'status':'physical','reason':'The Native traffic-light API may expose only a generic green state and no verified sole straight-arrow asset.'},
             'candidates':[]})
    (ROOT/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
