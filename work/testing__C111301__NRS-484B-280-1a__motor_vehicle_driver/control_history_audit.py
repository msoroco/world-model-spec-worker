"""Recompute Native wheelchair controller commands from sealed pre-control bodies."""
import hashlib
import json
import math
from pathlib import Path

from runner import control, encounter


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, delivery_receipt):
    attempt = Path(attempt)
    if delivery_receipt.get('format') != 'worker-delivery-audit' or delivery_receipt.get('passed') is not True:
        raise ValueError('passed source-audited delivery receipt required')
    acquisition = json.loads((attempt/'acquisition.json').read_text())
    seal = json.loads((attempt/'capture-seal.json').read_text())
    for name in ('encounter-history.jsonl', 'intersection-context.json'):
        digest = sha(attempt/name)
        if acquisition.get(name, {}).get('kind') != 'original_native' or acquisition[name].get('sha256') != digest:
            raise ValueError('original controller source missing or stale: ' + name)
        if seal.get('sources', {}).get(name) != digest:
            raise ValueError('sealed controller source missing or stale: ' + name)
        if delivery_receipt.get('measurement', {}).get('sources', {}).get(name) != digest:
            raise ValueError('delivery receipt controller source mismatch: ' + name)
    context = json.loads((attempt/'intersection-context.json').read_text())
    threshold = context.get('engineering_ttc_brake_s')
    bounds = context.get('ego_lane_bounds_y_m')
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or threshold <= 0:
        raise ValueError('original engineering policy missing')
    if not isinstance(bounds, list) or len(bounds) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) for x in bounds) or bounds[0] >= bounds[1]:
        raise ValueError('original lane bounds missing')
    scene = {'engineering_ttc_brake_s': threshold, 'ego_lane_bounds_y_m': bounds}
    rows = [json.loads(line) for line in (attempt/'encounter-history.jsonl').read_text().splitlines() if line.strip()]
    if len(rows) != delivery_receipt.get('frame_count') or len(rows) < 2:
        raise ValueError('controller history frame count mismatch')
    first_brake = None
    for row in rows:
        values = row.get('control_inputs', {})
        if not all(key in values for key in ('ego_body_vertices_m', 'person', 'manual_wheelchair', 'ego_speed_mps', 'pedestrian_speed_mps')):
            raise ValueError('pre-control original body or speed missing')
        if values['person'].get('source_ref') != context.get('person_asset_source') or values['manual_wheelchair'].get('source_ref') != context.get('manual_wheelchair_asset_source'):
            raise ValueError('pre-control person or chair identity differs from original context')
        observed = encounter(scene, values['ego_body_vertices_m'], values['person'],
                             values['manual_wheelchair'], values['ego_speed_mps'], values['pedestrian_speed_mps'])
        expected = control(scene, observed)
        if row.get('control_command') != expected or row.get('ego_brake') != expected['brake']:
            raise ValueError('recorded controller command differs from original body observation')
        if expected['brake'] and first_brake is None:
            first_brake = row['frame']
    if first_brake != delivery_receipt['measurement'].get('first_brake_frame'):
        raise ValueError('saved first-brake frame differs from original controller history')
    return {'format': 'worker-control-history-audit', 'passed': True,
            'frame_count': len(rows), 'first_brake_frame': first_brake,
            'source_sha256': sha(attempt/'encounter-history.jsonl'),
            'engineering_ttc_brake_s': threshold, 'legal_due_care_verdict': None}
