"""Measure curbside driving cues from synchronized original-source packets.

These measurements support review; they do not decide carelessness or prudence.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20


def require(value, message):
    if not value:
        raise ValueError(message)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(source):
    source = Path(source)
    paths = {name: source / name for name in
             ('native-ego-frames.jsonl', 'video_frames.jsonl', 'driving-context.json')}
    for name, path in paths.items():
        require(path.is_file(), 'Missing required source: ' + name)
    motion = rows(paths['native-ego-frames.jsonl'])
    mapping = rows(paths['video_frames.jsonl'])
    context = json.loads(paths['driving-context.json'].read_text())
    require(len(motion) == len(mapping) == FRAMES, 'Complete 600-frame source required')
    require(context.get('source_kind') in ('original_native', 'synthetic_native_sample'),
            'Native source provenance required')
    require(context.get('cell_id') == 'C230222' and
            context.get('law_id') == 'LVMC-11-22-020' and
            context.get('actor') == 'motor_vehicle_driver', 'Source identity differs')
    require(context.get('highway_in_city_evidence') in (None, 'original_source_reviewed'),
            'Highway context provenance invalid')
    measurements = []
    first_native = motion[0].get('native_frame')
    require(type(first_native) is int, 'First Native frame missing')
    previous_yaw = None
    for index, (item, frame) in enumerate(zip(motion, mapping)):
        expected_native = first_native + index
        expected_time = index / RATE
        require(item.get('source_kind') == context['source_kind'], 'Mixed motion provenance')
        require(item.get('native_frame') == frame.get('native_frame') == expected_native
                and frame.get('video_frame') == index, 'Native/video frame join differs')
        require(finite(item.get('time_s')) and finite(frame.get('time_s')) and
                abs(item['time_s'] - expected_time) < 1e-6 and
                abs(frame['time_s'] - expected_time) < 1e-6, '20 Hz time join differs')
        velocity = item.get('velocity_mps')
        acceleration = item.get('acceleration_mps2')
        require(all(type(vector) is list and len(vector) == 3 and
                    all(finite(v) for v in vector) for vector in (velocity, acceleration)),
                'Kinematic source incomplete')
        yaw = item.get('yaw_deg')
        gap = item.get('minimum_surface_gap_m')
        contact = item.get('contact')
        pedestrian = item.get('pedestrian_visible')
        require('minimum_surface_gap_m' in item and finite(yaw) and
                (gap is None or finite(gap) and gap >= 0) and
                (contact is None or type(contact) is bool) and
                (pedestrian is None or type(pedestrian) is bool),
                'Driving context source incomplete')
        speed = math.hypot(velocity[0], velocity[1])
        longitudinal = (acceleration[0] * velocity[0] + acceleration[1] * velocity[1]) / speed if speed > 0 else None
        yaw_rate = None if previous_yaw is None else ((yaw - previous_yaw + 180) % 360 - 180) * RATE
        measurements.append({'frame': index, 'native_frame': expected_native,
                             'time_s': expected_time, 'speed_mps': speed,
                             'longitudinal_acceleration_mps2': longitudinal,
                             'yaw_rate_degps': yaw_rate,
                             'minimum_surface_gap_m': gap, 'contact': contact,
                             'pedestrian_visible': pedestrian})
        previous_yaw = yaw
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    return {'format': 'c230222-curbside-driving-cues-v1',
            'source_kind': context['source_kind'], 'source_sha256': hashes,
            'sample_count': FRAMES, 'sampling_rate_hz': RATE,
            'highway_in_city_evidence': context['highway_in_city_evidence'],
            'measurements': measurements,
            'legal_carelessness_or_imprudence': None,
            'legal_review_required': True,
            'limitations': ['No engineering threshold defines careless or imprudent.',
                            'Motion cues alone do not establish municipal highway status.',
                            'Time to conflict requires participant trajectories and is not inferred here.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(measure(args.source), indent=2) + '\n')
