"""Exact authored placement-provenance source check; no authority claim."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / 'config.json').read_text())
    assignment_path = bundle / 'assignment-source.json'
    if sha(assignment_path) != 'e34b92fea95ce943c8bee703c64285f568f4c5cfdb0a6b6428072f57dd846ee0':
        raise ValueError('Frozen assignment source changed')
    assignment = json.loads(assignment_path.read_text())
    suffix = cfg['case_id'].rsplit('__', 1)[1]
    expected = {'placement_record_absent': False, 'placement_record_supplied': True}
    if suffix not in expected or cfg['case_id'] != assignment['assignment_id'] + '__' + suffix:
        raise ValueError('Wrong placement case identity')
    if (cfg['law_id'], cfg['cell_id'], cfg['actor']) != ('NRS-484B-300-1', 'C10389', 'motor_vehicle_driver'):
        raise ValueError('Wrong placement law, cell, or actor')
    if (cfg['rate_hz'], cfg['frames'], cfg['duration_s']) != (20, 600, 30):
        raise ValueError('Placement temporal contract changed')
    for key, name in (('road_sha256', 'alley-stop.xodr'), ('tracks_sha256', 'requested-tracks.jsonl'),
                      ('placement_record_sha256', 'placement-record.json')):
        if cfg[key] != sha(bundle / name):
            raise ValueError('Placement source hash changed: ' + name)
    signal = ET.parse(bundle / 'alley-stop.xodr').getroot().find('./road/signals/signal')
    if signal is None or (signal.get('id'), signal.get('type'), signal.get('s')) != ('3891', '206', '50'):
        raise ValueError('Placement device source differs')
    record = json.loads((bundle / 'placement-record.json').read_text())
    if (record.get('source_kind') != 'authored_cpu_context' or
            record.get('document_present') is not expected[suffix] or
            record.get('device_id') != '3891' or record.get('road_id') != 389 or
            record.get('official_placement_verified') is not False or
            record.get('administrative_authenticity_verified') is not False):
        raise ValueError('Placement provenance status differs')
    rows = [json.loads(line) for line in (bundle / 'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows) != 600 or any(row['frame'] != i or row['requested_officer_direction'] != 'none'
                               for i, row in enumerate(rows)):
        raise ValueError('Placement request window differs')
    if not any(row['requested_speed_mps'] == 0 for row in rows):
        raise ValueError('Placement pair must hold stop request fixed')
    return {'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'], 'frames': 600,
            'placement_source': record, 'placement_source_sha256': sha(bundle / 'placement-record.json'),
            'official_placement_verified': False, 'original_native_observed': False}
