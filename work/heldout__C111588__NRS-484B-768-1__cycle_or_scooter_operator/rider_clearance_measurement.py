"""Join original rider/participant trajectories for a clearance observation."""
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(attempt):
    root = Path(attempt)
    names = ('video_frames.jsonl', 'trace.jsonl', 'participant_motion.jsonl', 'clearance_samples.jsonl')
    paths = {name: root / name for name in names}
    for name, path in paths.items():
        if not path.is_file() or not path.read_bytes():
            raise ValueError('Missing required source: ' + name)
    mapping, rider, participant, samples = (_rows(paths[name]) for name in names)
    if len(mapping) < 3 or len({len(rows) for rows in (mapping, rider, participant, samples)}) != 1:
        raise ValueError('Clearance original/frame lengths differ')
    distances = []
    footprint_clearances = []
    radii = []
    for index, (frame, bike, other, sample) in enumerate(zip(mapping, rider, participant, samples)):
        identity = frame.get('carla_frame'), frame.get('time_s')
        if frame.get('video_frame') != index or any((row.get('frame'), row.get('time_s')) != identity for row in (bike, other, sample)):
            raise ValueError('Clearance original frame identity differs')
        if other.get('actor_id') != sample.get('participant_actor_id'):
            raise ValueError('Clearance participant identity differs')
        a, b = bike['position_m'], other['position_m']
        distance = hypot(float(a[0])-float(b[0]), float(a[1])-float(b[1]))
        reported = float(sample['center_distance_m'])
        if not isfinite(distance) or abs(distance-reported) > .01:
            raise ValueError('Clearance sample differs from original trajectories')
        distances.append(distance)
        rider_width = float(other['rider_half_width_m'])
        participant_width = float(other['participant_half_width_m'])
        if not all(isfinite(value) and 0 < value < 5 for value in (rider_width, participant_width)):
            raise ValueError('Invalid original body half-width readback')
        radius = rider_width + participant_width
        radii.append(radius)
        footprint_clearances.append(max(0.0, distance-radius))
    predictions = []
    for index in range(1, len(mapping)):
        dt = float(mapping[index]['time_s'])-float(mapping[index-1]['time_s'])
        if not isfinite(dt) or dt <= 0:
            raise ValueError('Invalid original participant frame time')
        closing = (distances[index-1]-distances[index])/dt
        if closing > .001 and distances[index] > radii[index]:
            predictions.append({'frame': mapping[index]['carla_frame'],
                                'time_s': mapping[index]['time_s'],
                                'time_to_conflict_s': footprint_clearances[index]/closing})
    ttc = min((item['time_to_conflict_s'] for item in predictions), default=None)
    return {'minimum_center_distance_m': min(distances),
            'minimum_body_footprint_clearance_m': min(footprint_clearances),
            'closest_approach_frame': mapping[distances.index(min(distances))]['carla_frame'],
            'time_to_conflict_s': ttc,
            'time_to_conflict_prediction_samples': predictions,
            'time_to_conflict_method': 'original per-frame planar closing rate to the sum of Native body half-width readbacks',
            'legal_reasonable_safety_judgment': None,
            'physical_participant_visibility_verified': False,
            'sources': {name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}}
