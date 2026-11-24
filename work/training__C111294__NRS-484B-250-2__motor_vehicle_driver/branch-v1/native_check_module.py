"""Validate one materialized branch Native request before CARLA execution."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle=Path(bundle)
    cfg=json.loads((bundle/'config.json').read_text())
    if cfg.get('format')!='c111294-2502-branch-native-request-v1':
        raise ValueError('Branch Native config format differs')
    if (cfg['road_sha256']!=sha(bundle/'crossroads.xodr') or
            cfg['tracks_sha256']!=sha(bundle/'requested-tracks.jsonl') or
            cfg['assignment_sha256']!=sha(bundle/'assignment-source.json') or
            cfg['case_plan_sha256']!=sha(bundle/'case-plan.json')):
        raise ValueError('Branch request source hash changed')
    law=json.loads((bundle/'assignment-source.json').read_text())['law']['text']
    if law!=cfg['source_text']:
        raise ValueError('Branch request law text changed')
    rows=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows)!=600 or cfg['frames']!=600 or cfg['rate_hz']!=20:
        raise ValueError('Branch request duration changed')
    for frame,row in enumerate(rows):
        if (row['frame']!=frame or row['time_s']!=frame/20 or
                row['authored_official_device_count']!=cfg['authored_official_device_count'] or
                row['requested_opposing_approaches']!=cfg['requested_opposing_approaches'] or
                row['requested_other_left_turn_intent']!=cfg['requested_other_left_turn_intent']):
            raise ValueError('Branch request track context changed')
    road=ET.parse(bundle/'crossroads.xodr').getroot()
    if len(road.findall('.//signal'))!=cfg['authored_official_device_count']:
        raise ValueError('Branch authored signal count changed')
    if cfg['original_native_observed'] or cfg['legal_verdict'] is not None:
        raise ValueError('Branch request asserted original or legal finding')
    return {'case_id':cfg['case_id'],'candidate':cfg['candidate_id'],
            'frames':600,'delivery_ready':False,'original_native_observed':False}
