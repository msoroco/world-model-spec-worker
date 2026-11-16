"""Independent source-shape and physical speed attainment review.

This auditor measures a recorded vehicle passage. It never decides whether the
statutory speed clause was violated.
"""
import hashlib
import json
import math
from pathlib import Path

LIFECYCLE = ('capture_finished', 'encoders_closed', 'restoration_verified',
             'native_exit', 'owner_released', 'saved_processing_started')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_lifecycle(events):
    require(tuple(events) == LIFECYCLE, 'Saved processing precedes Native ownership closure')
    return {'events': list(events), 'saved_processing_after_owner_release': True}


def classify(samples, frames, requested_mph):
    require(len(samples) == len(frames) == 480, 'Complete 480-frame Native source required')
    require(0 < requested_mph <= 100, 'Declared speed request required')
    speeds = []
    positions = []
    for index, (row, mapped) in enumerate(zip(samples, frames)):
        require(row.get('frame') == mapped.get('video_frame') == index and
                row.get('native_frame') == mapped.get('native_frame') and
                abs(row.get('time_s', -100) - mapped.get('time_s', 100)) <= 0.05,
                'Native/video frame-time join differs')
        require(row.get('ego_actor_id') and row.get('ego_role') == 'motor_vehicle_driver' and
                row.get('ego_blueprint', '').startswith('vehicle.') and
                len(row.get('ego_body_vertices_m', [])) >= 4 and
                row.get('other_actor_id') and
                row.get('other_blueprint', '').startswith('vehicle.') and
                len(row.get('other_body_vertices_m', [])) >= 4,
                'Vehicle participant identity or full body missing')
        velocity = row.get('ego_velocity_mps')
        position = row.get('ego_position_m')
        require(isinstance(velocity, list) and len(velocity) == 3 and
                isinstance(position, list) and len(position) == 3 and
                all(isinstance(value, (int, float)) and math.isfinite(value)
                    for value in velocity + position),
                'Original three-axis velocity or pose missing')
        speeds.append(math.sqrt(sum(value * value for value in velocity)) / 0.44704)
        positions.append(position)
    peak = max(speeds)
    displacement = math.dist(positions[0], positions[-1])
    attained = abs(peak - requested_mph) <= 0.75 and displacement >= 200
    return {'status': 'met' if attained else 'not_met',
            'requested_mph': requested_mph, 'measured_peak_mph': peak,
            'measured_displacement_m': displacement,
            'speed_tolerance_mph': 0.75,
            'measurement_interval_mph': [peak - 0.2, peak + 0.2],
            'legal_relation': 'unresolved_at_80_mph' if abs(peak - 80) <= 0.2
                              else 'not_assessed_by_physical_completion',
            'frames': len(samples)}


def audit_original(attempt, requested_mph):
    attempt = Path(attempt)
    source = attempt / 'native_samples.jsonl'
    mapping = attempt / 'video_frames.jsonl'
    require(source.is_file() and mapping.is_file(), 'Original Native speed source required')
    samples = read_rows(source)
    require(samples and all(row.get('source_kind') == 'original_native_capture'
                            for row in samples),
            'Original Native speed source required')
    result = classify(samples, read_rows(mapping), requested_mph)
    return {'physical_speed_completion': result,
            'source_sha256': {'native_samples.jsonl': sha(source),
                              'video_frames.jsonl': sha(mapping)},
            'original_source_verified': True,
            'legal_verdict_claimed': False}
