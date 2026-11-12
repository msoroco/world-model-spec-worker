"""Measure the lane of origin for an observed left turn from original Native rows.

The engineering angle is only a motion detector. It does not define statutory
preparation, designation, or a legal left-turn threshold.
"""

from hashlib import sha256
import json
from math import atan2, degrees, hypot, isfinite
from pathlib import Path


def _unit(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(type(x) not in
            (int, float) or not isfinite(x) for x in value):
        raise ValueError('Missing original ' + label)
    length = hypot(*value)
    if length < 1e-6:
        raise ValueError('Degenerate original ' + label)
    return value[0]/length, value[1]/length


def measure(path, *, left_detector_deg=60):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing required source: turn_origin_native.jsonl')
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) < 3:
        raise ValueError('Left-turn origin needs a continuous approach and turn')
    if not 30 <= left_detector_deg <= 120:
        raise ValueError('Left-turn detector must be an engineering angle')
    actor = rows[0].get('ego_id')
    if not actor:
        raise ValueError('Original turn source lacks actor identity')
    for index, row in enumerate(rows):
        if (row.get('ego_id') != actor or type(row.get('frame')) is not int or
                type(row.get('time_s')) not in (int, float) or
                not isfinite(row['time_s'])):
            raise ValueError('Original turn identity/frame/time differs')
        if index and (row['frame'] != rows[index-1]['frame']+1 or
                abs(row['time_s']-rows[index-1]['time_s']-.05) > 1e-4):
            raise ValueError('Original turn source is not continuous 20 Hz')
        _unit(row.get('ego_forward_xy'), 'ego heading')
    entries = [i for i, row in enumerate(rows) if row.get('is_junction') is True]
    if not entries or entries[0] == 0:
        raise ValueError('Left-turn source lacks approach')
    origin_index = entries[0]-1
    origin = rows[origin_index]
    if (any(row.get('is_junction') is not False for row in rows[:origin_index+1]) or
            entries != list(range(entries[0], entries[-1]+1)) or
            any(row.get('is_junction') is not False for row in rows[entries[-1]+1:])):
        raise ValueError('Left-turn source lacks a single junction entry')
    road_id, lane_id = origin.get('road_id'), origin.get('lane_id')
    center_road, center_lane = origin.get('center_turn_road_id'), origin.get('center_turn_lane_id')
    if any(type(v) is not int for v in (road_id, lane_id, center_road, center_lane)) or road_id != center_road or lane_id == 0 or center_lane == 0:
        raise ValueError('Original approach lacks designated lane identity')
    designation = origin.get('designation_source')
    marking_ids = origin.get('center_marking_source_ids',
                             origin.get('center_marking_actor_ids'))
    if not isinstance(designation, str) or not designation or not isinstance(marking_ids, list) or not marking_ids:
        raise ValueError('Original approach lacks center-lane designation source')
    if any(row.get('center_turn_lane_id') != center_lane or
           row.get('center_turn_road_id') != center_road or
           row.get('designation_source') != designation or
           row.get('center_marking_source_ids',
                   row.get('center_marking_actor_ids')) != marking_ids
           for row in rows[:origin_index+1]):
        raise ValueError('Center-lane designation changed during approach')
    heading = _unit(origin['ego_forward_xy'], 'approach heading')
    def deflection(row):
        x, y = _unit(row['ego_forward_xy'], 'ego heading')
        # CARLA +y is right for eastbound +x; a left turn has negative cross.
        return degrees(atan2(heading[0]*y-heading[1]*x,
                             heading[0]*x+heading[1]*y))
    turn_rows = rows[origin_index+1:]
    left = [row for row in turn_rows if deflection(row) <= -left_detector_deg]
    if not left:
        raise ValueError('No observed left deflection after approach')
    if any(deflection(row) >= left_detector_deg for row in turn_rows):
        raise ValueError('Observed turn direction changes to right')
    return {'format': 'worker-original-turn-origin-measurement',
            'source_sha256': sha256(raw).hexdigest(), 'ego_id': actor,
            'frame_count': len(rows), 'junction_entry_frame': rows[origin_index+1]['frame'],
            'approach_origin_frame': origin['frame'], 'approach_road_id': road_id,
            'approach_lane_id': lane_id, 'center_turn_lane_id': center_lane,
            'origin_matches_center_lane': lane_id == center_lane,
            'first_observed_left_frame': left[0]['frame'],
            'maximum_left_deflection_deg': -min(deflection(row) for row in turn_rows),
            'engineering_detector_deg': left_detector_deg,
            'designation_source': designation,
            'center_marking_source_ids': marking_ids,
            'designation_authority_verified': False,
            'physical_completion_verified': False,
            'legal_acceptance_claimed': False}
