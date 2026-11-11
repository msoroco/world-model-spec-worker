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


def measure(motion_path, signal_path, context_path):
    motion, motion_hash = _jsonl(motion_path, 'ego_turn_motion.jsonl')
    signals, signal_hash = _jsonl(signal_path, 'ego_signal_audio.jsonl')
    context, context_hash = _json(context_path, 'affected_participants.json')
    if len(motion) != len(signals) or len(motion) < 3:
        raise ValueError('Turn motion and signal histories differ or are incomplete')
    for key in ('pedestrian_may_be_affected', 'vehicle_may_be_affected'):
        if type(context.get(key)) is not bool or not context.get(key + '_source'):
            raise ValueError('Potentially affected participant needs separately cited context: ' + key)
    if not context.get('listener_id') or not context.get('listener_position_source'):
        raise ValueError('Listener audio needs a sourced location and identity')
    initial_yaw = float(motion[0]['ego_yaw_deg'])
    if not isfinite(initial_yaw):
        raise ValueError('Original turn yaw is not finite')
    observations = []
    previous = None
    for index, (movement, signal) in enumerate(zip(motion, signals)):
        frame, time_s = movement.get('frame'), movement.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError('Original turn frame/time identity missing')
        if previous is not None and (frame <= previous[0] or abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Original turn frames are not joined at 20 Hz')
        previous = frame, time_s
        if signal.get('frame') != frame or signal.get('time_s') != time_s:
            raise ValueError('Original signal/audio frame join failed')
        if signal.get('listener_id') != context['listener_id']:
            raise ValueError('Listener identity differs from sourced context')
        indicator = signal.get('indicator_readback')
        if indicator not in ('off', 'left', 'right'):
            raise ValueError('Turn indicator requires a Native side readback')
        yaw = float(movement['ego_yaw_deg'])
        if not isfinite(yaw):
            raise ValueError('Original turn yaw is not finite')
        delta = atan2(sin(radians(yaw - initial_yaw)), cos(radians(yaw - initial_yaw)))
        observations.append({'frame': frame, 'time_s': time_s,
                             'yaw_change_deg': delta * 180 / 3.141592653589793,
                             'indicator_readback': indicator,
                             'listener_audio_rms': _rms(signal.get('listener_audio_samples'))})
    onset = next((i for i, row in enumerate(observations)
                  if abs(row['yaw_change_deg']) > .5), None)
    if onset is None or onset == 0:
        raise ValueError('No measured turn onset after a direct course')
    before = observations[:onset]
    direction = 'left' if observations[onset]['yaw_change_deg'] > 0 else 'right'
    return {'format': 'worker-turn-signal-observation',
            'sources': {'ego_turn_motion.jsonl': motion_hash,
                        'ego_signal_audio.jsonl': signal_hash,
                        'affected_participants.json': context_hash},
            'frame_count': len(observations), 'turn_onset_frame': observations[onset]['frame'],
            'turn_direction': direction, 'pedestrian_may_be_affected': context['pedestrian_may_be_affected'],
            'vehicle_may_be_affected': context['vehicle_may_be_affected'],
            'max_pre_turn_listener_audio_rms': max(row['listener_audio_rms'] for row in before),
            'pre_turn_indicator_frames': [row['frame'] for row in before if row['indicator_readback'] == direction],
            'observations': observations, 'clearly_audible_legal_judgment': None,
            'reasonable_safety_legal_judgment': None,
            'appropriate_signal_legal_judgment': None}
