"""Measure recorded driving cues without inferring the driver's attention.

The 20 Hz Native trace and synchronized frame map are source inputs. Kinematics
are measurements; attention remains a separate original-source review question.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def angle_delta(now, prior):
    return (now - prior + 180) % 360 - 180


def measure(attempt):
    attempt = Path(attempt)
    trace_path = attempt / 'native-ego-frames.jsonl'
    map_path = attempt / 'video_frames.jsonl'
    context_path = attempt / 'native-driving-context.json'
    for path in (trace_path, map_path, context_path):
        require(path.is_file(), 'Missing required source: ' + path.name)
    trace, frames = rows(trace_path), rows(map_path)
    context = json.loads(context_path.read_text())
    require(len(trace) == len(frames) == FRAMES, 'Complete 600-frame source required')
    require(context.get('source_kind') in ('original_native', 'synthetic_native_sample'),
            'Source provenance required')
    require(set(context.get('camera_sources', {})) == set(VIEWS),
            'Four source-camera references required')
    for view, relative in context['camera_sources'].items():
        source = attempt / relative
        require(source.is_file() and source.suffix == '.mkv',
                'Missing camera source: ' + view)
    samples = []
    first_native = trace[0]['native_frame']
    prior = None
    for index, (motion, mapping) in enumerate(zip(trace, frames)):
        require(motion.get('source_kind') == context['source_kind'],
                'Mixed motion provenance')
        native = first_native + index
        require(motion.get('native_frame') == native and
                mapping.get('native_frame') == native and
                mapping.get('video_frame') == index,
                'Native/camera frame join differs')
        expected_time = index / RATE
        require(all(finite(value) and abs(value - expected_time) < 1e-5
                    for value in (motion.get('time_s'), mapping.get('time_s'))),
                '20 Hz source time join differs')
        position = motion.get('position_m')
        velocity = motion.get('velocity_mps')
        acceleration = motion.get('acceleration_mps2')
        yaw = motion.get('yaw_deg')
        require(all(isinstance(vector, list) and len(vector) == 3 and
                    all(finite(value) for value in vector)
                    for vector in (position, velocity, acceleration)) and finite(yaw),
                'Incomplete Native kinematic source')
        speed = math.hypot(*velocity[:2])
        yaw_rate = None if prior is None else angle_delta(yaw, prior) * RATE
        samples.append({'frame': index, 'native_frame': native,
                        'time_s': expected_time, 'position_m': position,
                        'yaw_deg': yaw, 'speed_mps': speed,
                        'yaw_rate_degps': yaw_rate,
                        'acceleration_mps2': acceleration})
        prior = yaw
    return {'format': 'c230222-attention-observation-v1',
            'source_kind': context['source_kind'], 'source_hashes': {
                trace_path.name: digest(trace_path), map_path.name: digest(map_path),
                context_path.name: digest(context_path),
                **{view: digest(attempt / relative)
                   for view, relative in context['camera_sources'].items()}},
            'sample_count': len(samples), 'sampling_rate_hz': RATE,
            'measurements': {'ego_pose': samples, 'ego_speed': [s['speed_mps'] for s in samples],
                             'ego_yaw_rate': [s['yaw_rate_degps'] for s in samples],
                             'ego_acceleration': [s['acceleration_mps2'] for s in samples]},
            'driver_attention_to_operation': None,
            'attention_review_required': True,
            'limitations': ['Vehicle motion alone does not establish driver attention.',
                            'Original driver-facing pixels and episode context require independent review.'],
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(measure(args.attempt), indent=2) + '\n')
