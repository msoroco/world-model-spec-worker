"""Saved-source measurements for LVMC 11.30.090; no legal verdict."""
import argparse
import json
import math
from pathlib import Path

RATE = 20
FRAMES = 600


def inside(point, polygon):
    x, y = point
    result = False
    for index, (ax, ay) in enumerate(polygon):
        bx, by = polygon[index - 1]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            result = not result
    return result


def measure(poses_path, geometry_path):
    rows = [json.loads(line) for line in Path(poses_path).read_text().splitlines()]
    geometry = json.loads(Path(geometry_path).read_text())
    if len(rows) != FRAMES or [r['video_frame'] for r in rows] != list(range(FRAMES)):
        raise ValueError('missing or unordered original pedestrian frames')
    if not all(rows[i]['native_frame'] < rows[i+1]['native_frame'] for i in range(FRAMES-1)):
        raise ValueError('nonmonotonic original Native frames')
    if not all(abs(r['time_s'] - i / RATE) < .005 for i, r in enumerate(rows)):
        raise ValueError('missing original 20 Hz timing')
    if geometry.get('sidewalk_provided') is not True or geometry.get('adjacent') is not True:
        raise ValueError('provided adjacent sidewalk source missing')
    survey = geometry.get('native_readback')
    if not isinstance(survey, dict) or not all(len(survey.get(name, [])) == 3 for name in ('roadway', 'sidewalk')):
        raise ValueError('Native roadway/sidewalk survey source missing')
    road = geometry['roadway_xy_m']
    walk = geometry['sidewalk_xy_m']
    if len(road) < 3 or len(walk) < 3:
        raise ValueError('original roadway or sidewalk polygon missing')
    centers = [r['pedestrian_xy_m'] for r in rows]
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in centers):
        raise ValueError('invalid original pedestrian position')
    road_occupied = [inside(p, road) for p in centers]
    walk_occupied = [inside(p, walk) for p in centers]
    path_m = sum(math.dist(a, b) for a, b in zip(centers, centers[1:]))
    long_m = centers[-1][0] - centers[0][0]
    lateral_m = centers[-1][1] - centers[0][1]
    return {'required_source_kind': 'original_native_pose_and_native_geometry_readback',
            'frames': FRAMES, 'roadway_occupied_frames': sum(road_occupied),
            'sidewalk_occupied_frames': sum(walk_occupied), 'path_length_m': path_m,
            'longitudinal_displacement_m': long_m, 'lateral_displacement_m': lateral_m,
            'along_to_lateral_ratio': abs(long_m) / max(abs(lateral_m), 1e-9),
            'roadway_intervals': intervals(road_occupied),
            'sidewalk_intervals': intervals(walk_occupied),
            'legal_conclusion': None,
            'physical_review_required': True}


def intervals(values):
    out = []
    start = None
    for i, value in enumerate([*values, False]):
        if value and start is None:
            start = i
        if not value and start is not None:
            out.append([start, i - 1])
            start = None
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--poses', required=True)
    parser.add_argument('--geometry', required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.poses, args.geometry), sort_keys=True))
