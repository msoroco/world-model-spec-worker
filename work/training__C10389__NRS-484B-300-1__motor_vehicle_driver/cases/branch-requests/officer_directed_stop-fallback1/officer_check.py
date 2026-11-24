"""Offline identity and request check for C10389 officer-direction contrast."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle=Path(bundle);cfg=json.loads((bundle/'config.json').read_text())
    a=json.loads((bundle/'assignment-source.json').read_text())
    if sha(bundle/'assignment-source.json')!='e34b92fea95ce943c8bee703c64285f568f4c5cfdb0a6b6428072f57dd846ee0':
        raise ValueError('Frozen assignment source changed')
    if a['law_id']!='NRS-484B-300-1' or a['cell_id']!='C10389' or a['actor']!='motor_vehicle_driver':
        raise ValueError('Wrong law, cell, or actor')
    suffix=cfg['case_id'].rsplit('__',1)[1]
    if suffix not in ('officer_no_direction_stop','officer_no_direction_proceed','officer_directed_stop','officer_directed_proceed') or cfg['case_id']!=a['assignment_id']+'__'+suffix:
        raise ValueError('Wrong officer case identity')
    direction='none' if suffix.startswith('officer_no_direction_') else 'proceed'
    stop=suffix.endswith('_stop')
    if cfg['requested_officer_direction']!=direction or cfg['rate_hz']!=20 or cfg['frames']!=600 or cfg['duration_s']!=30:
        raise ValueError('Officer direction or temporal contract changed')
    for key,name in [('road_sha256','alley-stop.xodr'),('tracks_sha256','requested-tracks.jsonl')]:
        if cfg[key]!=sha(bundle/name):raise ValueError('Officer source hash changed: '+name)
    signal=ET.parse(bundle/'alley-stop.xodr').getroot().find('./road/signals/signal')
    if signal is None or signal.get('id')!='3891' or signal.get('type')!='206' or signal.get('s')!='50':
        raise ValueError('Authored stop landmark changed')
    rows=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows)!=600 or any(row.get('frame')!=i or row.get('requested_officer_direction')!=direction for i,row in enumerate(rows)):
        raise ValueError('Officer request frame/direction differs')
    if stop and not any(row['requested_speed_mps']==0 for row in rows):
        raise ValueError('Stop request absent')
    if not stop and not any(row['requested_ego_x_m']>50 for row in rows):
        raise ValueError('Crossing request absent')
    return {'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
            'requested_officer_direction':direction,'frames':600,'police_authority_verified':False,
            'original_native_observed':False}
