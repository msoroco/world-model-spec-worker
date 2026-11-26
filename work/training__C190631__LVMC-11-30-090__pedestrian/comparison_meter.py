"""Source-bound CPU comparison of walking surfaces; no legal outcome."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(road_poses, road_geometry, walk_poses, walk_geometry):
    from native.measure import measure

    if sha(road_geometry) != sha(walk_geometry):
        raise ValueError('Compared overpass geometry differs')
    road = measure(road_poses, road_geometry)
    sidewalk = measure(walk_poses, walk_geometry)
    if road['frames'] != 600 or sidewalk['frames'] != 600:
        raise ValueError('Compared durations differ')
    if not (road['roadway_occupied_frames'] > road['sidewalk_occupied_frames'] and
            sidewalk['sidewalk_occupied_frames'] > sidewalk['roadway_occupied_frames']):
        raise ValueError('Walking surface difference not measured')
    if not math.isclose(road['path_length_m'], sidewalk['path_length_m'], abs_tol=1):
        raise ValueError('Compared longitudinal travel differs')
    if not math.isclose(road['longitudinal_displacement_m'],
                        sidewalk['longitudinal_displacement_m'], abs_tol=1):
        raise ValueError('Compared route length differs')
    return {'format': 'worker-surface-meter-comparison',
            'source_hashes': {'road_poses': sha(road_poses), 'walk_poses': sha(walk_poses),
                              'geometry': sha(road_geometry)},
            'fixed': {'frames': 600, 'geometry_sha256': sha(road_geometry),
                      'path_length_difference_m': abs(road['path_length_m'] - sidewalk['path_length_m'])},
            'deliberate_difference': {'roadway_occupied_frames': road['roadway_occupied_frames'],
                                      'sidewalk_occupied_frames': sidewalk['sidewalk_occupied_frames']},
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('road_poses', 'road_geometry', 'walk_poses', 'walk_geometry'):
        parser.add_argument('--' + name.replace('_', '-'), required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.road_poses, args.road_geometry,
                             args.walk_poses, args.walk_geometry), sort_keys=True))
