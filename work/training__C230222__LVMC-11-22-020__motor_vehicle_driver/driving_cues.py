"""Measure curbside driving cues from synchronized original-source packets.

These measurements support review; they do not decide carelessness or prudence.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from body_geometry import constant_velocity_time_to_overlap, planar_gap

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
             ('native-ego-frames.jsonl', 'native-body-geometry.jsonl',
              'native-collision-events.jsonl', 'video_frames.jsonl',
              'driving-context.json')}
    for name, path in paths.items():
        require(path.is_file(), 'Missing required source: ' + name)
    motion = rows(paths['native-ego-frames.jsonl'])
    geometry = rows(paths['native-body-geometry.jsonl'])
    collision_events = rows(paths['native-collision-events.jsonl'])
    mapping = rows(paths['video_frames.jsonl'])
    context = json.loads(paths['driving-context.json'].read_text())
    require(len(motion) == len(mapping) == len(geometry) == FRAMES,
            'Complete 600-frame source required')
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
    event_frames = set()
    for event in collision_events:
        require(event.get('source_kind') == context['source_kind'] and
                type(event.get('native_frame')) is int and
                type(event.get('other_actor_id')) is int and
                type(event.get('other_actor_type')) is str,
                'Collision event source invalid')
        event_frames.add(event['native_frame'])
    for index, (item, frame, body) in enumerate(zip(motion, mapping, geometry)):
        expected_native = first_native + index
        expected_time = index / RATE
        require(item.get('source_kind') == context['source_kind'], 'Mixed motion provenance')
        require(body.get('source_kind') == context['source_kind'] and
                body.get('native_frame') == expected_native and
                finite(body.get('time_s')) and
                abs(body['time_s'] - expected_time) < 1e-6,
                'Original body geometry join differs')
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
        ttc = item.get('time_to_conflict_s')
        contact = item.get('contact')
        pedestrian = item.get('pedestrian_visible')
        require('minimum_surface_gap_m' in item and finite(yaw) and
                (gap is None or finite(gap) and gap >= 0) and
                'time_to_conflict_s' in item and
                (ttc is None or finite(ttc) and ttc >= 0) and
                (contact is None or type(contact) is bool) and
                (pedestrian is None or type(pedestrian) is bool),
                'Driving context source incomplete')
        own = body.get('ego_footprint_xy_m')
        participants = body.get('participants')
        require(type(participants) is list and type(own) is list,
                'Original body geometry missing')
        original_gaps = []
        original_ttc = []
        for participant in participants:
            require(type(participant.get('actor_id')) is int and
                    type(participant.get('type_id')) is str and
                    participant['type_id'].startswith(('vehicle.', 'walker.')),
                    'Original participant identity missing')
            measured_gap = planar_gap(own, participant.get('footprint_xy_m'))
            require(finite(participant.get('planar_gap_m')) and
                    abs(measured_gap - participant['planar_gap_m']) < 1e-5,
                    'Participant gap differs from original body corners')
            original_gaps.append(measured_gap)
            predicted = constant_velocity_time_to_overlap(
                own, body.get('ego_velocity_xy_mps'),
                participant['footprint_xy_m'], participant.get('velocity_xy_mps'))
            require(predicted == participant.get('constant_velocity_time_to_overlap_s'),
                    'Participant time-to-overlap differs from original body velocities')
            if predicted is not None:
                original_ttc.append(predicted)
        computed_gap = min(original_gaps, default=None)
        computed_ttc = min(original_ttc, default=None)
        require(body.get('gap_method') ==
                'original_native_2d_body_footprint_separation' and
                body.get('minimum_surface_gap_m') == computed_gap and
                gap == computed_gap, 'Motion gap differs from original body geometry')
        require(body.get('minimum_constant_velocity_time_to_overlap_s') == computed_ttc and
                ttc == computed_ttc,
                'Motion time-to-conflict proxy differs from original body velocities')
        if contact is True:
            require(expected_native in event_frames,
                    'Contact cue lacks original collision event')
        if context['source_kind'] == 'original_native':
            require(contact is not False, 'Absence of a collision event is unknown')
        speed = math.hypot(velocity[0], velocity[1])
        longitudinal = (acceleration[0] * velocity[0] + acceleration[1] * velocity[1]) / speed if speed > 0 else None
        yaw_rate = None if previous_yaw is None else ((yaw - previous_yaw + 180) % 360 - 180) * RATE
        measurements.append({'frame': index, 'native_frame': expected_native,
                             'time_s': expected_time, 'speed_mps': speed,
                             'longitudinal_acceleration_mps2': longitudinal,
                             'yaw_rate_degps': yaw_rate,
                             'minimum_surface_gap_m': gap, 'contact': contact,
                             'constant_velocity_time_to_conflict_s': ttc,
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
                            'Planar box clearance is not a 3D collision or legal conclusion.',
                            'Time to conflict is a 30-second constant-velocity planar-body proxy; it is not observed future motion or a legal cutoff.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(measure(args.source), indent=2) + '\n')
