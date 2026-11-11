"""Join original rider turn motion to reviewed source-video signal frames.

This measures whether a visible signal was observed before turn onset, including
one-frame signals. It does not decide appropriateness, safety or exceptions.
"""

from hashlib import sha256
import json
from math import atan2, cos, isfinite, radians, sin
from pathlib import Path


DEVICES = ('bicycle', 'electric_bicycle', 'electric_scooter')


def _rows(path, name):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original source: ' + name)
    raw = path.read_bytes()
    try:
        return [json.loads(line) for line in raw.splitlines()], sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original source: ' + name) from error


def measure(motion_path, review_path, context_path, video_path):
    motion, motion_sha = _rows(motion_path, 'rider_motion.jsonl')
    reviews, review_sha = _rows(review_path, 'rider_signal_review.jsonl')
    context_path, video_path = Path(context_path), Path(video_path)
    if not context_path.is_file() or not context_path.read_bytes():
        raise ValueError('Missing original source: rider_context.json')
    if not video_path.is_file() or not video_path.read_bytes():
        raise ValueError('Missing original source: driver_reference.mkv')
    context_raw, video_sha = context_path.read_bytes(), sha256(video_path.read_bytes()).hexdigest()
    try:
        context = json.loads(context_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original rider context') from error
    if len(motion) < 3 or len(motion) != len(reviews):
        raise ValueError('Original rider motion/signal review incomplete')
    if context.get('device_type') not in DEVICES or not context.get('device_type_source'):
        raise ValueError('Rider device type needs original source')
    if context.get('on_roadway') is not True or not context.get('roadway_source'):
        raise ValueError('Roadway activation needs original source')
    for key in ('designated_turn_lane', 'both_hands_required_for_safety'):
        item = context.get(key)
        if not isinstance(item, dict) or 'value' not in item:
            raise ValueError('Signal exception context missing: ' + key)
        value, source = item['value'], item.get('source_ref')
        if value is not None and (type(value) is not bool or not isinstance(source, str) or not source):
            raise ValueError('Known signal exception needs source: ' + key)
        if value is None and source is not None:
            raise ValueError('Unknown signal exception cannot cite verdict: ' + key)
    observations = []
    prior = None
    initial_yaw = None
    rider_id = context.get('rider_id')
    if not rider_id:
        raise ValueError('Original rider identity missing')
    for motion_row, review in zip(motion, reviews):
        frame, time_s = motion_row.get('frame'), motion_row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError('Original rider frame/time invalid')
        if prior is not None and (frame != prior[0] + 1 or abs(time_s - prior[1] - .05) > 1e-4):
            raise ValueError('Original rider frames are not joined at 20 Hz')
        prior = frame, time_s
        if (review.get('frame'), review.get('time_s'), review.get('rider_id')) != (frame, time_s, rider_id):
            raise ValueError('Original signal/video frame or rider join failed')
        if review.get('source_video_sha256') != video_sha:
            raise ValueError('Signal review no longer binds retained video')
        visible = review.get('visible_signal')
        if visible is not None and type(visible) is not bool:
            raise ValueError('Signal visibility review invalid')
        signal = review.get('signal_type')
        if signal not in ('left_arm', 'right_arm', 'none', 'unknown'):
            raise ValueError('Signal type review invalid')
        if visible is True and signal not in ('left_arm', 'right_arm'):
            raise ValueError('Visible signal needs observed arm direction')
        try:
            yaw = float(motion_row['rider_yaw_deg'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Original rider yaw missing') from error
        if not isfinite(yaw):
            raise ValueError('Original rider yaw invalid')
        if initial_yaw is None:
            initial_yaw = yaw
        delta = atan2(sin(radians(yaw - initial_yaw)), cos(radians(yaw - initial_yaw))) * 180 / 3.141592653589793
        observations.append({'frame': frame, 'time_s': time_s,
                             'heading_change_deg': delta,
                             'visible_signal': visible,
                             'signal_type': signal})
    onset = next((i for i, row in enumerate(observations)
                  if abs(row['heading_change_deg']) > .5), None)
    if onset is None or onset == 0:
        raise ValueError('No measured rider turn onset')
    before = observations[:onset]
    return {'format': 'worker-rider-turn-signal-observation',
            'sources': {'rider_motion.jsonl': motion_sha,
                        'rider_signal_review.jsonl': review_sha,
                        'rider_context.json': sha256(context_raw).hexdigest(),
                        video_path.name: video_sha},
            'device_type': context['device_type'],
            'turn_onset_frame': observations[onset]['frame'],
            'pre_turn_visible_signal_frames': [row['frame'] for row in before
                                               if row['visible_signal'] is True],
            'pre_turn_signal_observation_complete': all(row['visible_signal'] is not None
                                                        for row in before),
            'signal_exception_context': {key: context[key] for key in
                                         ('designated_turn_lane', 'both_hands_required_for_safety')},
            'observations': observations,
            'appropriate_signal_legal_judgment': None,
            'reasonable_safety_legal_judgment': None,
            'both_hands_safety_legal_judgment': None}
