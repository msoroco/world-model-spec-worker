"""Measure straight travel and candidate center-lane use from original rows."""

from hashlib import sha256
import json
from math import atan2, degrees, isfinite
from pathlib import Path

from turn_origin_measurement import _unit


def measure(path, *, straight_detector_deg=20):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing required source: turn_origin_native.jsonl')
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) < 3 or not 5 <= straight_detector_deg <= 30:
        raise ValueError('Straight-use source or engineering detector invalid')
    actor = rows[0].get('ego_id')
    entries = [i for i, row in enumerate(rows) if row.get('is_junction') is True]
    if not actor or not entries or entries[0] == 0 or entries[-1] == len(rows)-1:
        raise ValueError('Straight-use source lacks actor, approach or exit')
    if entries != list(range(entries[0], entries[-1]+1)):
        raise ValueError('Straight-use junction interval differs')
    for i, row in enumerate(rows):
        if (row.get('ego_id') != actor or type(row.get('frame')) is not int or
                type(row.get('time_s')) not in (int, float) or
                not isfinite(row['time_s'])):
            raise ValueError('Original straight identity/frame/time differs')
        if i and (row['frame'] != rows[i-1]['frame']+1 or
                abs(row['time_s']-rows[i-1]['time_s']-.05) > 1e-4):
            raise ValueError('Original straight source is not continuous 20 Hz')
        _unit(row.get('ego_forward_xy'), 'ego heading')
    origin = rows[entries[0]-1]
    if any(row.get('is_junction') is not False for row in rows[:entries[0]]+rows[entries[-1]+1:]):
        raise ValueError('Straight-use source lacks single junction interval')
    road, lane = origin.get('road_id'), origin.get('lane_id')
    center_road, center_lane = origin.get('center_turn_road_id'), origin.get('center_turn_lane_id')
    if any(type(v) is not int for v in (road, lane, center_road, center_lane)) or road != center_road or lane == 0 or center_lane == 0:
        raise ValueError('Original straight approach lacks center-lane identity')
    marking = origin.get('center_marking_source_ids')
    designation = origin.get('designation_source')
    if not isinstance(marking, list) or not marking or not isinstance(designation, str) or not designation:
        raise ValueError('Original straight approach lacks marking source')
    for row in rows[:entries[0]]:
        if (row.get('center_turn_road_id'), row.get('center_turn_lane_id'),
                row.get('center_marking_source_ids'), row.get('designation_source')) != (
                center_road, center_lane, marking, designation):
            raise ValueError('Original straight marking identity changed')
    hx, hy = _unit(origin['ego_forward_xy'], 'approach heading')
    deflection = []
    for row in rows[entries[0]:]:
        x, y = _unit(row['ego_forward_xy'], 'ego heading')
        deflection.append(abs(degrees(atan2(hx*y-hy*x, hx*x+hy*y))))
    maximum = max(deflection)
    if maximum > straight_detector_deg:
        raise ValueError('Original motion is not straight under engineering detector')
    return {'format': 'worker-original-straight-use-measurement',
            'source_sha256': sha256(raw).hexdigest(), 'ego_id': actor,
            'frame_count': len(rows), 'junction_entry_frame': rows[entries[0]]['frame'],
            'approach_origin_frame': origin['frame'], 'approach_road_id': road,
            'approach_lane_id': lane, 'center_turn_lane_id': center_lane,
            'origin_matches_center_lane': lane == center_lane,
            'straight_motion_observed': True,
            'maximum_deflection_deg': maximum,
            'engineering_detector_deg': straight_detector_deg,
            'designation_source': designation,
            'center_marking_source_ids': marking,
            'designation_authority_verified': False,
            'physical_completion_verified': False,
            'legal_acceptance_claimed': False}
