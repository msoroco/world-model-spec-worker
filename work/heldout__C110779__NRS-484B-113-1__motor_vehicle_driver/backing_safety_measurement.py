"""Original-frame backing and surrounding-user measurements for NRS 484B.113(1).

Reverse motion, separation, deceleration and contact are observations. They do
not decide reasonable safety or interference with other traffic.
"""

from hashlib import sha256
import json
from math import atan2, degrees, hypot, isfinite
from pathlib import Path


def _rows(path, label):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original source: ' + label)
    raw = path.read_bytes()
    try:
        return [json.loads(line) for line in raw.splitlines()], sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original source: ' + label) from error


def _body(item, label):
    try:
        values = tuple(float(item[key]) for key in ('x_m', 'y_m', 'body_radius_m'))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Missing original body geometry: ' + label) from error
    if not all(isfinite(v) for v in values) or values[2] <= 0:
        raise ValueError('Invalid original body geometry: ' + label)
    return values


def _vector(item, label):
    if not isinstance(item, list) or len(item) != 2:
        raise ValueError('Missing original vector: ' + label)
    try:
        values = tuple(float(v) for v in item)
    except (TypeError, ValueError) as error:
        raise ValueError('Invalid original vector: ' + label) from error
    if not all(isfinite(v) for v in values):
        raise ValueError('Invalid original vector: ' + label)
    return values


def measure(motion_path, contact_path, context_path):
    motion, motion_sha = _rows(motion_path, 'backing_motion.jsonl')
    contacts, contact_sha = _rows(contact_path, 'backing_contacts.jsonl')
    context_path = Path(context_path)
    if not context_path.is_file() or not context_path.read_bytes():
        raise ValueError('Missing original source: backing_context.json')
    context_raw = context_path.read_bytes()
    try:
        context = json.loads(context_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original backing context') from error
    if len(motion) < 3 or len(contacts) != len(motion):
        raise ValueError('Original backing motion/contact history incomplete')
    participants = context.get('participants')
    if not isinstance(participants, dict) or not participants:
        raise ValueError('Surrounding traffic context required')
    for actor_id, item in participants.items():
        if not isinstance(actor_id, str) or not actor_id or not isinstance(item, dict) or (
                item.get('kind') not in ('vehicle', 'pedestrian') or
                not item.get('position_motion_purpose_source') or
                not item.get('highway_use_source')):
            raise ValueError('Each surrounding user needs independently cited context')
    observations = []
    prior = None
    speeds = {}
    prior_gaps = {}
    for row, contact in zip(motion, contacts):
        frame, time_s = row.get('frame'), row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError('Original backing frame/time invalid')
        if prior is not None and (frame != prior[0] + 1 or abs(time_s - prior[1] - .05) > 1e-4):
            raise ValueError('Original backing frames are not joined at 20 Hz')
        prior = frame, time_s
        if (contact.get('frame'), contact.get('time_s')) != (frame, time_s):
            raise ValueError('Original contact/motion frame join failed')
        contact_ids = contact.get('contact_actor_ids')
        if not isinstance(contact_ids, list) or len(contact_ids) != len(set(contact_ids)) or (
                set(contact_ids) - set(participants)):
            raise ValueError('Original contact actor identities invalid')
        ego = _body(row.get('ego'), 'ego')
        heading = _vector(row.get('ego_heading_xy'), 'ego heading')
        velocity = _vector(row.get('ego_velocity_xy'), 'ego velocity')
        hnorm = hypot(*heading)
        if hnorm < 1e-6:
            raise ValueError('Original backing heading degenerate')
        longitudinal = (heading[0] * velocity[0] + heading[1] * velocity[1]) / hnorm
        bodies = row.get('participants')
        if not isinstance(bodies, dict) or set(bodies) != set(participants):
            raise ValueError('Original surrounding actor identities differ')
        gap, bearing, acceleration_by_actor, time_to_conflict = {}, {}, {}, {}
        for actor_id in participants:
            other = _body(bodies[actor_id], actor_id)
            dx, dy = other[0] - ego[0], other[1] - ego[1]
            gap[actor_id] = hypot(dx, dy) - ego[2] - other[2]
            if gap[actor_id] <= 0:
                time_to_conflict[actor_id] = 0.0
            elif actor_id in prior_gaps:
                closing_speed = (prior_gaps[actor_id] - gap[actor_id]) / .05
                time_to_conflict[actor_id] = gap[actor_id] / closing_speed if closing_speed > 0 else None
            else:
                time_to_conflict[actor_id] = None
            prior_gaps[actor_id] = gap[actor_id]
            bearing[actor_id] = degrees(atan2(heading[0] * dy - heading[1] * dx,
                                                heading[0] * dx + heading[1] * dy))
            try:
                speed = float(bodies[actor_id]['speed_mps'])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError('Original surrounding speed missing') from error
            if not isfinite(speed) or speed < 0:
                raise ValueError('Original surrounding speed invalid')
            if actor_id in speeds:
                acceleration = (speed - speeds[actor_id]) / .05
                acceleration_by_actor[actor_id] = acceleration
            else:
                acceleration_by_actor[actor_id] = None
            speeds[actor_id] = speed
        observations.append({'frame': frame, 'time_s': time_s,
                             'ego_longitudinal_speed_mps': longitudinal,
                             'backing_observed': longitudinal < 0,
                             'surface_gaps_m': gap, 'relative_bearings_deg': bearing,
                             'sampled_time_to_conflict_s': time_to_conflict,
                             'participant_acceleration_mps2': acceleration_by_actor,
                             'contact_actor_ids': contact_ids})
    backing = [row for row in observations if row['backing_observed']]
    first, last = (backing[0]['frame'], backing[-1]['frame']) if backing else (None, None)
    if backing and len(backing) != last - first + 1:
        raise ValueError('Backing motion has an unreviewed interruption')
    window = [row for row in observations if first is not None and first <= row['frame'] <= last]
    return {'format': 'worker-backing-safety-observation',
            'sources': {'backing_motion.jsonl': motion_sha,
                        'backing_contacts.jsonl': contact_sha,
                        'backing_context.json': sha256(context_raw).hexdigest()},
            'backing_onset_frame': first, 'backing_end_frame': last,
            'minimum_surface_gap_during_backing_m': {
                actor_id: min((row['surface_gaps_m'][actor_id] for row in window),
                              default=None)
                for actor_id in participants},
            'minimum_sampled_time_to_conflict_during_backing_s': {
                actor_id: min((row['sampled_time_to_conflict_s'][actor_id]
                               for row in window if row['sampled_time_to_conflict_s'][actor_id] is not None),
                              default=None)
                for actor_id in participants},
            'contact_frames_during_backing': [row['frame'] for row in window
                                              if row['contact_actor_ids']],
            'minimum_sampled_surrounding_acceleration_during_backing_mps2': {
                actor_id: min((row['participant_acceleration_mps2'][actor_id]
                               for row in window if row['participant_acceleration_mps2'][actor_id] is not None),
                              default=None)
                for actor_id in participants},
            'participant_context': participants, 'observations': observations,
            'reasonable_safety_legal_judgment': None,
            'interference_legal_judgment': None}
