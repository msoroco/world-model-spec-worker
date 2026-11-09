"""Independently recompute exact copied C10374 requests and pair controls."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
CASE=HERE.parent.parent
ROOT=CASE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines()]


def audit():
    from build import CASES,POLICIES,ZONE,LAW
    construction=read(HERE/'manifest.json')
    copied=read(HERE/'offline/manifest.json')
    proof=read(HERE/'offline/proof-compatibility.json')
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    if (read(assignment)['law_record']['text']!=LAW or
        read(plan)['source_law']['text']!=LAW or
        construction['assignment_sha256']!=sha(assignment) or
        construction['case_plan_sha256']!=sha(plan) or
        construction['road_sha256']!=sha(HERE/'alley-zone.xodr') or
        construction['capture_sha256']!=sha(HERE/'capture.py') or
        construction['measurement_contract_sha256']!=sha(HERE/'measurement-contract.json') or
        construction['saved_sha256']!=sha(HERE/'saved.py') or
        construction['fixture_raw_sha256']!=sha(HERE/'fixture_raw.py') or
        construction['route_fallbacks_sha256']!=sha(HERE/'route_fallbacks.py') or
        copied['construction_sha256']!=sha(HERE/'manifest.json') or
        proof['positives']!=8 or proof['negatives']!=48 or len(copied['entries'])!=8):
        raise ValueError('construction source/proof')
    by_pair={}
    total=0
    for entry in copied['entries']:
        bundle=HERE/entry['bundle'];suffix=bundle.parent.name;candidate=bundle.name
        sources={'assignment-source.json':assignment,'case-plan.json':plan,
            'alley-zone.xodr':HERE/'alley-zone.xodr',
            'config.json':HERE/'drafts'/suffix/candidate/'config.json',
            'requested-tracks.jsonl':HERE/'drafts'/suffix/candidate/'requested-tracks.jsonl',
            'build.py':HERE/'build.py','check.py':HERE/'check.py',
            'capture.py':HERE/'capture.py',
            'measurement-contract.json':HERE/'measurement-contract.json',
            'saved.py':HERE/'saved.py','fixture_raw.py':HERE/'fixture_raw.py',
            'route_fallbacks.py':HERE/'route_fallbacks.py'}
        if set(entry['file_sha256'])!=set(sources):raise ValueError('copy set')
        for name,source in sources.items():
            if sha(bundle/name)!=sha(source) or entry['file_sha256'][name]!=sha(source):
                raise ValueError('copied file '+name)
        cfg=read(bundle/'config.json');track=rows(bundle/'requested-tracks.jsonl')
        if suffix not in CASES or candidate not in POLICIES or len(track)!=240:
            raise ValueError('case and track count')
        root=ET.parse(bundle/'alley-zone.xodr').getroot()
        lanes=root.findall('./road/lanes/laneSection/right/lane')
        if root.find('./road').get('id')!='374' or \
           [(lane.get('id'),lane.get('type')) for lane in lanes]!=[
               ('-1','driving'),('-2','driving')]:
            raise ValueError('Native alley lanes')
        speed,camera,stop=POLICIES[candidate]
        through=suffix==CASES[0]
        if cfg['zone_rectangle_xy_m']!=list(ZONE) or \
           cfg['requested_zone_route'] is not through or \
           cfg['requested_ego_speed_mps']!=speed or \
           cfg['camera_policy']!=camera or cfg['stop_x_m']!=stop:
            raise ValueError('candidate comparison controls')
        for i,row in enumerate(track):
            t=(i+1)/20;x=round(min(stop if stop is not None else 150,5+speed*t),6)
            y=-1.75 if through else -5.25
            if row['frame']!=i or row['time_s']!=t or \
               row['requested_ego_x_m']!=x or row['requested_ego_y_m']!=y or \
               row['requested_lane_id']!=(-1 if through else -2) or \
               row['actual_zone_overlap_observed'] is not False:
                raise ValueError('independent request row')
            total+=1
        by_pair.setdefault(candidate,{})[suffix]=(speed,camera,stop,len(track))
    if len(by_pair)!=4 or any(set(pair)!=set(CASES) or
                              pair[CASES[0]]!=pair[CASES[1]]
                              for pair in by_pair.values()):
        raise ValueError('four controlled pairs')
    return {'format':'c10374-safety-zone-independent-package-audit-v1',
            'copied_bundles':8,'controlled_pairs':4,'rows_recomputed':total,
            'positive':8,'tamper_negative':48,'physical_zone_verified':False,
            'delivery_ready':False}


if __name__=='__main__':print(json.dumps(audit()))
