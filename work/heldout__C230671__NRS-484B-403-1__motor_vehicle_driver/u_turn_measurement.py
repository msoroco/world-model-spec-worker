"""Original-frame U-turn motion and surrounding-user safety observations.

This measures geometry over the maneuver without deciding whether it was safe
or whether a cited cross-reference prohibits the turn.
"""

from hashlib import sha256
import json
from math import atan2, cos, hypot, isfinite, radians, sin
from pathlib import Path


PROHIBITIONS = ('NRS-484B-403-2', 'NRS-484B-403-3', 'NRS-484B-227-1',
                'NRS-484B-363-3', 'NRS-484B-407')


def _load(path, name):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original source: ' + name)
    raw = path.read_bytes()
    try:
        return json.loads(raw) if path.suffix == '.json' else [json.loads(line) for line in raw.splitlines()], sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original source: ' + name) from error


def _body(body, label):
    try:
        values = tuple(float(body[key]) for key in ('x_m', 'y_m', 'body_radius_m'))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Missing original body geometry: ' + label) from error
    if not all(isfinite(v) for v in values) or values[2] <= 0:
        raise ValueError('Invalid original body geometry: ' + label)
    return values


def measure(motion_path, context_path):
    rows, motion_sha = _load(motion_path, 'u_turn_motion.jsonl')
    context, context_sha = _load(context_path, 'u_turn_context.json')
    if not isinstance(rows, list) or len(rows) < 3 or not isinstance(context, dict):
        raise ValueError('Original U-turn source incomplete')
    prohibitions = context.get('prohibitions')
    if not isinstance(prohibitions, dict) or set(prohibitions) != set(PROHIBITIONS):
        raise ValueError('Every cited U-turn prohibition needs context')
    for name, item in prohibitions.items():
        if not isinstance(item, dict) or 'value' not in item:
            raise ValueError('Cited prohibition context missing: ' + name)
        value, source = item['value'], item.get('source_ref')
        if value is not None and (type(value) is not bool or not isinstance(source, str) or not source):
            raise ValueError('Known prohibition needs cited source: ' + name)
        if value is None and source is not None:
            raise ValueError('Unknown prohibition cannot assert a source verdict: ' + name)
    roles = context.get('participant_roles')
    if not isinstance(roles, dict) or not roles:
        raise ValueError('Original surrounding participant roles required')
    for name, item in roles.items():
        if not isinstance(name, str) or not name or not isinstance(item, dict) or (
                item.get('role') not in ('oncoming', 'following', 'other') or
                not item.get('source_ref')):
            raise ValueError('Participant role needs a cited original source')
    start_yaw = None
    previous = None
    observations = []
    minimum_gap = {actor_id: float('inf') for actor_id in roles}
    minimum_accel = {actor_id: None for actor_id in roles}
    previous_speeds = {}
    for row in rows:
        frame, time_s = row.get('frame'), row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError('Original U-turn frame/time invalid')
        if previous is not None and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Original U-turn frames are not joined at 20 Hz')
        previous = frame, time_s
        ego = _body(row.get('ego'), 'ego')
        bodies = row.get('participants')
        if not isinstance(bodies, dict) or set(bodies) != set(roles):
            raise ValueError('Original U-turn participant identities differ')
        try:
            yaw = float(row['ego_yaw_deg'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Original U-turn yaw missing') from error
        if not isfinite(yaw):
            raise ValueError('Original U-turn yaw invalid')
        if start_yaw is None:
            start_yaw = yaw
        delta = atan2(sin(radians(yaw - start_yaw)), cos(radians(yaw - start_yaw))) * 180 / 3.141592653589793
        gaps = {}
        for actor_id in roles:
            body = _body(bodies[actor_id], actor_id)
            gap = hypot(ego[0] - body[0], ego[1] - body[1]) - ego[2] - body[2]
            gaps[actor_id] = gap
            minimum_gap[actor_id] = min(minimum_gap[actor_id], gap)
            try:
                speed = float(bodies[actor_id]['speed_mps'])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError('Original participant speed missing') from error
            if not isfinite(speed) or speed < 0:
                raise ValueError('Original participant speed invalid')
            if actor_id in previous_speeds:
                accel = (speed - previous_speeds[actor_id]) / .05
                old = minimum_accel[actor_id]
                minimum_accel[actor_id] = accel if old is None else min(old, accel)
            previous_speeds[actor_id] = speed
        observations.append({'frame': frame, 'time_s': time_s,
                             'heading_change_deg': delta, 'surface_gaps_m': gaps})
    onset = next((index for index, row in enumerate(observations)
                  if abs(row['heading_change_deg']) > .5), None)
    if onset is None or onset == 0:
        raise ValueError('No measured U-turn heading-change onset')
    return {'format': 'worker-u-turn-observation',
            'sources': {'u_turn_motion.jsonl': motion_sha,
                        'u_turn_context.json': context_sha},
            'turn_onset_frame': observations[onset]['frame'],
            'last_observed_frame': observations[-1]['frame'],
            'net_heading_change_deg': observations[-1]['heading_change_deg'],
            'participant_minimum_surface_gap_m': minimum_gap,
            'participant_minimum_sampled_acceleration_mps2': minimum_accel,
            'participant_roles': roles, 'prohibition_context': prohibitions,
            'observations': observations,
            'safe_turn_legal_judgment': None,
            'prohibition_legal_judgments': None}
