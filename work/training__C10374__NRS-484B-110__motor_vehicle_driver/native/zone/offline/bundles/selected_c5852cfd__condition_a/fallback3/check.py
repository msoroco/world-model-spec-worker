"""Exact offline check of the authored C10374 zone comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from build import CASES, LAW, POLICIES, ZONE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle/'config.json').read_text())
    source = json.loads((bundle/'assignment-source.json').read_text())
    plan = json.loads((bundle/'case-plan.json').read_text())
    suffix = cfg['case_id'].split('__')[-2]+'__'+cfg['case_id'].split('__')[-1]
    candidate = cfg['candidate_id']
    if (suffix not in CASES or candidate not in POLICIES or
            cfg['case_id'] != cfg['assignment_id']+'__'+suffix or
            source['law_record']['text'] != LAW or
            plan['source_law']['text'] != LAW):
        raise ValueError('exact law/case source')
    if (cfg['assignment_sha256'] != sha(bundle/'assignment-source.json') or
            cfg['case_plan_sha256'] != sha(bundle/'case-plan.json') or
            cfg['road_sha256'] != sha(bundle/'alley-zone.xodr') or
            cfg['tracks_sha256'] != sha(bundle/'requested-tracks.jsonl')):
        raise ValueError('copied source hashes')
    root = ET.parse(bundle/'alley-zone.xodr').getroot()
    roads = root.findall('./road')
    if len(roads) != 1 or roads[0].get('id') != '374' or \
       [(lane.get('id'), lane.get('type')) for lane in roads[0].findall('./lanes/laneSection/right/lane')] != \
           [('-1','driving'),('-2','driving')]:
        raise ValueError('alley lane topology')
    speed,camera,stop = POLICIES[candidate]
    through = suffix == CASES[0]
    if (cfg['requested_zone_route'] is not through or
            cfg['requested_ego_speed_mps'] != speed or cfg['camera_policy'] != camera or
            cfg['stop_x_m'] != stop or cfg['zone_rectangle_xy_m'] != list(ZONE) or
            cfg['physical_zone_designation_verified'] is not False or
            cfg['actual_zone_overlap_observed'] is not False):
        raise ValueError('candidate policy or unverified zone status')
    tracks = rows(bundle/'requested-tracks.jsonl')
    if len(tracks) != 240:
        raise ValueError('240-frame request')
    encounter = 0
    for i,row in enumerate(tracks):
        t=(i+1)/20
        x=round(min(stop if stop is not None else 150,5+speed*t),6)
        y=-1.75 if through else -5.25
        if (row['frame'] != i or row['time_s'] != t or
                row['requested_ego_x_m'] != x or row['requested_ego_y_m'] != y or
                row['requested_lane_id'] != (-1 if through else -2) or
                row['requested_zone_route'] is not through or
                row['physical_zone_designation_verified'] is not False or
                row['actual_zone_overlap_observed'] is not False):
            raise ValueError('request row differs')
        encounter += int(ZONE[0] <= x <= ZONE[1])
    if candidate == 'fallback3' and encounter != 0 or \
       candidate != 'fallback3' and encounter == 0:
        raise ValueError('pass/stop request geometry')
    return {'case_id':cfg['case_id'],'candidate_id':candidate,
            'requested_zone_route':through,'requested_encounter_frames':encounter,
            'actual_zone_overlap_observed':False,'delivery_ready':False}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=Path.cwd())
    a=p.parse_args();print(json.dumps(check(a.bundle)))
