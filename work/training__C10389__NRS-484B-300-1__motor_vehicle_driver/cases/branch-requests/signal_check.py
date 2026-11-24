"""Offline identity and request check for a C10389 signal Native attempt."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle=Path(bundle)
    cfg=json.loads((bundle/'config.json').read_text())
    assignment=json.loads((bundle/'assignment-source.json').read_text())
    if sha(bundle/'assignment-source.json')!='e34b92fea95ce943c8bee703c64285f568f4c5cfdb0a6b6428072f57dd846ee0':
        raise ValueError('Frozen assignment source changed')
    if assignment['law_id']!='NRS-484B-300-1' or assignment['cell_id']!='C10389' or assignment['actor']!='motor_vehicle_driver':
        raise ValueError('Wrong law, cell, or actor')
    suffix=cfg['case_id'].rsplit('__',1)[1]
    if suffix not in ('signal_red_stop','signal_red_proceed','signal_green_stop','signal_green_proceed') or cfg['case_id']!=assignment['assignment_id']+'__'+suffix:
        raise ValueError('Wrong signal case identity')
    aspect='red' if suffix.startswith('signal_red_') else 'green'
    stop=suffix.endswith('_stop')
    if cfg['requested_signal_aspect']!=aspect or cfg['rate_hz']!=20 or cfg['frames']!=600 or cfg['duration_s']!=30:
        raise ValueError('Signal aspect or temporal contract changed')
    for key,name in [('road_sha256','alley-stop.xodr'),('tracks_sha256','requested-tracks.jsonl')]:
        if cfg[key]!=sha(bundle/name):
            raise ValueError('Signal source hash changed: '+name)
    signal=ET.parse(bundle/'alley-stop.xodr').getroot().find('./road/signals/signal')
    if signal is None or signal.get('id')!='3892' or signal.get('type')!='1000001' or signal.get('dynamic')!='yes' or signal.get('s')!='50':
        raise ValueError('Authored signal identity changed')
    rows=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows)!=600 or any(row.get('frame')!=i or row.get('requested_signal_aspect')!=aspect for i,row in enumerate(rows)):
        raise ValueError('Signal request frame/aspect differs')
    if stop and not any(row['requested_speed_mps']==0 for row in rows):
        raise ValueError('Stop request absent')
    if not stop and not any(row['requested_ego_x_m']>50 for row in rows):
        raise ValueError('Crossing request absent')
    return {'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
            'requested_signal_aspect':aspect,'frames':600,'original_native_observed':False}
