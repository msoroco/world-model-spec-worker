"""Self-contained source audit for a materialized exact right-pass bundle."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

NATIVE=Path(__file__).resolve().parent
CONFIG=json.loads((NATIVE/'config.json').read_text())
ROOT=Path(CONFIG['assignment_id'])


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def audit():
    cfg=CONFIG
    road=NATIVE/'right-pass-road.xodr'
    track=NATIVE/'requested-tracks.jsonl'
    assignment=NATIVE/'assignment-source.json'
    plan=NATIVE/'case-plan.json'
    manifest=json.loads((NATIVE/'manifest.json').read_text())
    require(cfg['assignment_id']==ROOT.name and cfg['case_id'].startswith(ROOT.name+'__') and
            cfg['law_id']=='NRS-484B-210-2' and cfg['cell_id']=='C146314' and
            cfg['actor']=='motor_vehicle_driver' and cfg['rate_hz']==20 and
            cfg['frames']==240 and cfg['duration_s']==12 and
            cfg['selected_case_id']==cfg['case_id'] and
            cfg['road_sha256']==sha(road) and cfg['tracks_sha256']==sha(track) and
            cfg['assignment_sha256']==sha(assignment) and
            cfg['case_plan_sha256']==sha(plan) and
            cfg['original_native_observed'] is False and
            cfg['legal_safety_verdict'] is None,
            'Exact selected identity or current source differs')
    law=json.loads(assignment.read_text())['law']
    require(law['id']=='NRS-484B-210-2' and
            law['text']==json.loads(plan.read_text())['source_law_text'],
            'Frozen law text differs')
    lane_nodes=ET.parse(road).findall('.//laneSection/right/lane')
    require([(node.get('id'),node.get('type')) for node in lane_nodes]==
            [('-1','driving'),('-2','driving')],
            'Native right-pass road lanes differ')
    entries=manifest.get('entries',[])
    require(len(entries)==1 and entries[0]=={
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'config_sha256':sha(NATIVE/'config.json'),
        'tracks_sha256':sha(track)} and
        manifest.get('road_sha256')==sha(road) and
        manifest.get('assignment_sha256')==sha(assignment) and
        manifest.get('case_plan_sha256')==sha(plan),
        'Exact selected source manifest differs')
    samples=rows(track)
    require(len(samples)==240,'Selected right-pass duration differs')
    for i,row in enumerate(samples):
        require(row['frame']==i and row['time_s']==(i+1)/20 and
                row['case_id']==cfg['case_id'] and
                row['candidate_id']==cfg['candidate_id'] and
                row['source_kind']=='authored_native_request' and
                row['road_id']==210 and row['lead_lane_id']==-1 and
                row['ego_lane_id'] in (-1,-2) and
                all(math.isfinite(row[k]) for k in
                    ('ego_x_m','ego_y_m','lead_x_m','lead_y_m')) and
                row['actual_pass_observed'] is False and
                row['actual_clearance_observed'] is False and
                row['legal_safety_verdict'] is None,
                'Selected right-pass source row differs')
    require(any(row['ego_lane_id']==-2 for row in samples) and
            any(row['ego_x_m']>row['lead_x_m'] and
                row['ego_y_m']<row['lead_y_m'] for row in samples),
            'Selected right-side pass never requested')
    return {'candidates':1,'case_id':cfg['case_id'],
            'candidate_id':cfg['candidate_id'],
            'original_native_observed':False,'legal_safety_verdict':None}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
