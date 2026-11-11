"""Join original turn motion, lamp readback and listener audio samples.

Audio energy is an observation at a declared listener, not a legal threshold
for "clearly audible". Potentially affected participants remain sourced context.
"""

from hashlib import sha256
import json
from math import atan2, cos, isfinite, sin, sqrt, radians
from pathlib import Path


def _json(path, label):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + label)
    raw = path.read_bytes()
    if not raw:
        raise ValueError('Empty required source: ' + label)
    try:
        return json.loads(raw), sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid required source: ' + label) from error


def _jsonl(path, label):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + label)
    raw = path.read_bytes()
    if not raw:
        raise ValueError('Empty required source: ' + label)
    try:
        return [json.loads(line) for line in raw.splitlines()], sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid required source: ' + label) from error


def _rms(samples):
    if not isinstance(samples, list) or len(samples) < 8:
        raise ValueError('Original listener audio needs at least eight samples per frame')
    values = [float(value) for value in samples]
    if any(not isfinite(value) or abs(value) > 1 for value in values):
        raise ValueError('Original listener audio sample is out of range')
    return sqrt(sum(value * value for value in values) / len(values))


def _body(row, label):
    try:
        x, y, radius = (float(row[key]) for key in ('x_m', 'y_m', 'body_radius_m'))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Missing original body geometry: ' + label) from error
    if not all(isfinite(value) for value in (x, y, radius)) or radius <= 0:
        raise ValueError('Invalid original body geometry: ' + label)
    return x, y, radius


def _closing_proxy(ego_now, ego_prev, other_now, other_prev, dt):
    """Closest constant-velocity approach; descriptive, never a safety decision."""
    rx, ry = other_now[0] - ego_now[0], other_now[1] - ego_now[1]
    vx = (other_now[0] - other_prev[0] - ego_now[0] + ego_prev[0]) / dt
    vy = (other_now[1] - other_prev[1] - ego_now[1] + ego_prev[1]) / dt
    speed2 = vx * vx + vy * vy
    if speed2 < 1e-12:
        return {'closest_approach_time_s': None, 'projected_surface_gap_m': None}
    time_s = max(0.0, -(rx * vx + ry * vy) / speed2)
    gap = sqrt((rx + vx * time_s) ** 2 + (ry + vy * time_s) ** 2) - ego_now[2] - other_now[2]
    return {'closest_approach_time_s': time_s, 'projected_surface_gap_m': gap}


def measure(motion_path, signal_path, context_path, participant_path):
    motion, motion_hash = _jsonl(motion_path, 'ego_turn_motion.jsonl')
    signals, signal_hash = _jsonl(signal_path, 'ego_signal_audio.jsonl')
    context, context_hash = _json(context_path, 'affected_participants.json')
    participants, participant_hash = _jsonl(participant_path, 'participant_bodies.jsonl')
    if len(motion) != len(signals) or len(motion) < 3:
        raise ValueError('Turn motion and signal histories differ or are incomplete')
    if len(participants) != len(motion):
        raise ValueError('Original participant bodies differ from turn frames')
    for key in ('pedestrian_may_be_affected', 'vehicle_may_be_affected'):
        if type(context.get(key)) is not bool or not context.get(key + '_source'):
            raise ValueError('Potentially affected participant needs separately cited context: ' + key)
    if not context.get('listener_id') or not context.get('listener_position_source'):
        raise ValueError('Listener audio needs a sourced location and identity')
    actor_types = context.get('participant_types')
    if not isinstance(actor_types, dict) or not actor_types or any(
        kind not in ('pedestrian', 'vehicle') for kind in actor_types.values()
    ) or not context.get('participant_geometry_source'):
        raise ValueError('Participant identities, types and original geometry source required')
    initial_yaw = float(motion[0]['ego_yaw_deg'])
    if not isfinite(initial_yaw):
        raise ValueError('Original turn yaw is not finite')
    observations = []
    previous = None
    body_series = {actor_id: [] for actor_id in actor_types}
    ego_series = []
    for index, (movement, signal, participant) in enumerate(zip(motion, signals, participants)):
        frame, time_s = movement.get('frame'), movement.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError('Original turn frame/time identity missing')
        if previous is not None and (frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Original turn frames are not joined at 20 Hz')
        previous = frame, time_s
        if signal.get('frame') != frame or signal.get('time_s') != time_s:
            raise ValueError('Original signal/audio frame join failed')
        if participant.get('frame') != frame or participant.get('time_s') != time_s:
            raise ValueError('Original participant/body frame join failed')
        bodies = participant.get('bodies')
        if not isinstance(bodies, dict) or set(bodies) != set(actor_types):
            raise ValueError('Original participant identities differ from sourced context')
        ego_series.append(_body(movement, 'ego'))
        for actor_id in actor_types:
            body_series[actor_id].append(_body(bodies[actor_id], actor_id))
        if signal.get('listener_id') != context['listener_id']:
            raise ValueError('Listener identity differs from sourced context')
        indicator = signal.get('indicator_readback')
        if indicator not in ('off', 'left', 'right'):
            raise ValueError('Turn indicator requires a Native side readback')
        yaw = float(movement['ego_yaw_deg'])
        if not isfinite(yaw):
            raise ValueError('Original turn yaw is not finite')
        delta = atan2(sin(radians(yaw - initial_yaw)), cos(radians(yaw - initial_yaw)))
        samples = signal.get('listener_audio_samples')
        if samples is None:
            if (context['pedestrian_may_be_affected'] or
                    signal.get('listener_audio_status') != 'not_collected_no_affected_pedestrian'):
                raise ValueError('Original listener audio required when a pedestrian may be affected')
            audio_rms = None
        else:
            audio_rms = _rms(samples)
        observations.append({'frame': frame, 'time_s': time_s,
                             'yaw_change_deg': delta * 180 / 3.141592653589793,
                             'indicator_readback': indicator,
                             'listener_audio_rms': audio_rms})
    onset = next((i for i, row in enumerate(observations)
                  if abs(row['yaw_change_deg']) > .5), None)
    if onset is None or onset == 0:
        raise ValueError('No measured turn onset after a direct course')
    before = observations[:onset]
    direction = 'left' if observations[onset]['yaw_change_deg'] > 0 else 'right'
    clearance = {}
    for actor_id, series in body_series.items():
        gaps = [sqrt((ego[0] - other[0]) ** 2 + (ego[1] - other[1]) ** 2)
                - ego[2] - other[2] for ego, other in zip(ego_series, series)]
        clearance[actor_id] = {
            'type': actor_types[actor_id],
            'minimum_sampled_surface_gap_m': min(gaps),
            'surface_gap_at_turn_onset_m': gaps[onset],
            'constant_velocity_proxy_at_turn_onset': _closing_proxy(
                ego_series[onset], ego_series[onset - 1], series[onset],
                series[onset - 1], .05),
        }
    return {'format': 'worker-turn-signal-observation',
            'sources': {'ego_turn_motion.jsonl': motion_hash,
                        'ego_signal_audio.jsonl': signal_hash,
                        'affected_participants.json': context_hash,
                        'participant_bodies.jsonl': participant_hash},
            'frame_count': len(observations), 'turn_onset_frame': observations[onset]['frame'],
            'turn_direction': direction, 'pedestrian_may_be_affected': context['pedestrian_may_be_affected'],
            'vehicle_may_be_affected': context['vehicle_may_be_affected'],
            'max_pre_turn_listener_audio_rms': max((row['listener_audio_rms'] for row in before
                                                   if row['listener_audio_rms'] is not None), default=None),
            'pre_turn_indicator_frames': [row['frame'] for row in before if row['indicator_readback'] == direction],
            'participant_clearance': clearance,
            'observations': observations, 'clearly_audible_legal_judgment': None,
            'reasonable_safety_legal_judgment': None,
            'appropriate_signal_legal_judgment': None}
