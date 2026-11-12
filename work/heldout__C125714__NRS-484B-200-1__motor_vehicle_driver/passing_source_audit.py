"""Independent original-source audit of proposed same-direction overtaking."""

import argparse
import hashlib
import json
from math import hypot
from pathlib import Path


def _rows(path):
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(attempt):
    attempt = Path(attempt)
    passing_path = attempt / 'passing_actors.jsonl'
    roadway_path = attempt / 'directed_roadway_footprints.jsonl'
    passing, roadway = _rows(passing_path), _rows(roadway_path)
    if len(passing) < 3 or len(passing) != len(roadway):
        raise ValueError('Passing/roadway source length mismatch')
    actor_ids, relative = None, []
    for index, (actors, road) in enumerate(zip(passing, roadway)):
        if actors['frame'] != road['frame'] or abs(actors['time_s']-road['time_s']) > 1e-4:
            raise ValueError('Passing/roadway frame or time mismatch')
        if index and (actors['frame'] != passing[index-1]['frame'] + 1 or
                      abs(actors['time_s']-passing[index-1]['time_s']-.05) > 1e-4):
            raise ValueError('Passing source not continuous at 20 Hz')
        if actors.get('passing_law_verified') is not False:
            raise ValueError('Passing source claims unproved legal conditions')
        subject, lead = actors['subject'], actors['lead']
        ids = subject['actor_id'], lead['actor_id']
        if ids[0] == ids[1] or (actor_ids is not None and ids != actor_ids):
            raise ValueError('Passing actor identity changed')
        actor_ids = ids
        if road.get('ego_id') != ids[0]:
            raise ValueError('Passing subject identity differs from roadway source')
        if any(not item['blueprint_id'].startswith('vehicle.') for item in (subject, lead)):
            raise ValueError('Passing actor is not a vehicle')
        corners = road.get('ego_corners', [])
        if len(corners) != 4 or any(
                not min(point[axis] for point in corners)-.1 <= subject['position_m'][axis]
                <= max(point[axis] for point in corners)+.1 for axis in (0, 1)):
            raise ValueError('Passing subject does not occupy original roadway footprint')
        tangent = road['travel_tangent_xy']
        norm = hypot(*tangent)
        if not .99 <= norm <= 1.01:
            raise ValueError('Roadway travel tangent invalid')
        for item in (subject, lead):
            velocity = item['velocity_mps']
            if velocity[0]*tangent[0] + velocity[1]*tangent[1] <= 0:
                raise ValueError('Passing vehicle did not travel in selected direction')
        delta = [subject['position_m'][i]-lead['position_m'][i] for i in (0,1)]
        relative.append(delta[0]*tangent[0]+delta[1]*tangent[1])
    if relative[0] >= 0 or relative[-1] <= 0:
        raise ValueError('Original actors do not show behind-to-ahead order change')
    return {'format': 'worker-passing-original-source-audit',
            'frames': [row['frame'] for row in passing], 'actor_ids': list(actor_ids),
            'relative_longitudinal_m': relative,
            'passing_source_sha256': hashlib.sha256(passing_path.read_bytes()).hexdigest(),
            'roadway_source_sha256': hashlib.sha256(roadway_path.read_bytes()).hexdigest(),
            'passing_law_verified': False, 'delivery_ready': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.attempt), indent=2) + '\n')


if __name__ == '__main__':
    main()
