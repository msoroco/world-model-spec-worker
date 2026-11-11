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
    return {'minimum_center_distance_m': min(distances),
            'closest_approach_frame': mapping[distances.index(min(distances))]['carla_frame'],
            'time_to_conflict_s': None, 'legal_reasonable_safety_judgment': None,
            'physical_participant_visibility_verified': False,
            'sources': {name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}}
