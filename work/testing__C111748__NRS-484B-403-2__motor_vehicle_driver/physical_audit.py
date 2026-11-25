"""Independent physical engineering outcome from original Native frames.

The diagnostic probe generates synthetic rows; its result never claims a CARLA
attempt or a legal conclusion. Production calls the same measurement on sealed
original rows after media/source review.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path


def assess(path: Path, case_id: str) -> dict:
    path = Path(path)
    if not path.is_file():
        return _result('unverified', {'device-native.json': 'missing'}, {}, ['device-native.json'])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sources = {'device-native.json': digest}
    packet = json.loads(path.read_text())
    if packet.get('case_id') != case_id:
        return _result('unverified', sources, {}, ['exact case identity'])
    rows = packet.get('frames')
    if not isinstance(rows, list) or len(rows) != 900:
        return _result('unverified', sources, {}, ['900 original Native frames'])
    try:
        frames = [row['frame'] for row in rows]
        times = [row['time_s'] for row in rows]
        if any(frame != frames[0] + index for index, frame in enumerate(frames)) or any(
                not math.isfinite(time) or abs((time - times[0]) - index / 20) > .002
                for index, time in enumerate(times)):
            raise ValueError('original frame/time join')
        device = packet['device']
        visible = [row['frame'] for row in rows
                   if row['ego']['approach_id'] == device['governed_approach'] and
                   row['device_readback']['device_id'] == device['device_id'] and
                   row['device_readback']['prohibits_u_turn'] == device['prohibits_u_turn'] and
                   row['device_readback']['visible_to_ego'] is True]
        if not visible:
            raise ValueError('governed device observation')
        turns = [row['frame'] for row in rows if row['ego']['u_turn_in_progress'] is True]
        start, end = rows[0]['ego'], rows[-1]['ego']
        reversal = abs((end['yaw_deg'] - start['yaw_deg'] + 180) % 360 - 180)
        complete_turn = (bool(turns) and min(visible) < min(turns) and
                         start['road_id'] == end['road_id'] and
                         start['lane_id'] != end['lane_id'] and reversal >= 135)
    except (KeyError, TypeError, ValueError) as exc:
        return _result('unverified', sources, {}, [str(exc)])
    expected_turn = case_id.endswith('__prohibited_attempt') or case_id.endswith('__neutral_device_turn')
    met = complete_turn if expected_turn else not turns
    observables = {'first_governed_visible_frame': min(visible),
                   'first_turn_frame': min(turns) if turns else None,
                   'observed_turn': bool(turns), 'completed_reversal': bool(complete_turn),
                   'heading_reversal_deg': reversal,
                   'start_lane_id': start['lane_id'], 'end_lane_id': end['lane_id'],
                   'sample_count': len(rows)}
    return _result('met' if met else 'not_met', sources, observables, [])


def _result(status: str, sources: dict, observables: dict, missing: list[str]) -> dict:
    method = 'independent original Native governed-device and ego motion assessment'
    return {'physical_checks': {'maneuver': {'status': status, 'method': method,
            'sources': sources, 'missing_evidence': missing,
            'legal_verdict_claimed': False}},
            'maneuver_completed': status == 'met',
            'realized_observables': observables,
            'legal_verdict_claimed': False}
