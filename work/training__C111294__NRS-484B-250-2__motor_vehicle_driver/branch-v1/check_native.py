"""Verify source-bound original-Native branch requests before selection."""
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
REPO=BASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(suffix,candidate):
    bundle=HERE/suffix/candidate/'native-request'
    config=json.loads((bundle/'config.json').read_text())
    source=HERE/suffix/'sources'
    if config['case_id']!=BASE.name+'__'+suffix or config['candidate_id']!=candidate:
        raise ValueError('Branch Native request identity mismatch')
    if ((bundle/'assignment-source.json').read_bytes()!=
            (REPO/'inputs'/BASE.name/'assignment.json').read_bytes() or
            (bundle/'case-plan.json').read_bytes()!=(BASE/'case-plan.json').read_bytes() or
            config['assignment_sha256']!=sha(bundle/'assignment-source.json') or
            config['case_plan_sha256']!=sha(bundle/'case-plan.json')):
        raise ValueError('Branch Native request input changed')
    if (config['road_sha256']!=sha(bundle/'crossroads.xodr') or
            (bundle/'crossroads.xodr').read_bytes()!=(source/'road.xodr').read_bytes() or
            config['tracks_sha256']!=sha(bundle/'requested-tracks.jsonl')):
        raise ValueError('Branch Native request road/track hash changed')
    road=ET.parse(bundle/'crossroads.xodr').getroot()
    signals=road.findall('.//signal')
    if len(signals)!=config['authored_official_device_count']:
        raise ValueError('Branch authored signal inventory changed')
    rows=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    history=json.loads((source/'actor-history.json').read_text())['rows']
    if len(rows)!=600 or len(history)!=600 or config['frames']!=600 or config['rate_hz']!=20:
        raise ValueError('Branch request frame contract changed')
    for index,(row,actor) in enumerate(zip(rows,history)):
        if (row['frame']!=index or row['time_s']!=index/20 or
                row['requested_other_xyz_m']!=actor['other']['center_xyz_m'] or
                row['requested_other_left_turn_intent']!=actor['other_left_turn_intent'] or
                row['requested_opposing_approaches']!=actor['opposing_approaches'] or
                row['authored_official_device_count']!=actor['authored_official_device_count']):
            raise ValueError('Branch request/source geometry changed')
    if config['original_native_observed'] or config['legal_verdict'] is not None:
        raise ValueError('Branch request asserted observed or legal outcome')
    return {'case_id':config['case_id'],'candidate':candidate,'frames':600,
            'request_sha256':sha(bundle/'config.json'),
            'tracks_sha256':sha(bundle/'requested-tracks.jsonl'),
            'original_native_observed':False,'legal_verdict':None}


if __name__=='__main__':
    if len(sys.argv)!=3:
        raise SystemExit('suffix and candidate required')
    print(json.dumps(check(sys.argv[1],sys.argv[2]),sort_keys=True))
