"""Native lane readback and source-review join for the no-signal turn-lane case."""
from hashlib import sha256
import json
from pathlib import Path


def capture_lane(world_map, location, frame, time_s):
    waypoint = world_map.get_waypoint(location)
    if waypoint is None:
        raise ValueError('No Native roadway waypoint at rider')
    left = getattr(waypoint, 'left_lane_marking', None)
    right = getattr(waypoint, 'right_lane_marking', None)
    return {'frame': frame, 'time_s': time_s, 'road_id': waypoint.road_id,
            'lane_id': waypoint.lane_id, 'lane_type': str(waypoint.lane_type),
            'is_junction': bool(waypoint.is_junction),
            'left_marking_type': str(left.type) if left else None,
            'right_marking_type': str(right.type) if right else None,
            'designation_from_map': None}


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(attempt):
    root = Path(attempt)
    names = ('video_frames.jsonl', 'lane_waypoint_readback.jsonl',
             'turn_lane_marking_review.jsonl', 'driver_reference.mkv')
    paths = {name: root / name for name in names}
    for name, path in paths.items():
        if not path.is_file() or not path.read_bytes():
            raise ValueError('Missing required source: ' + name)
    mapping, lanes, reviews = (_rows(paths[name]) for name in names[:3])
    if len(mapping) < 3 or len(mapping) != len(lanes) or len(mapping) != len(reviews):
        raise ValueError('Turn-lane original frame lengths differ')
    video_sha = sha256(paths['driver_reference.mkv'].read_bytes()).hexdigest()
    visible_frames = []
    for index, (frame, lane, review) in enumerate(zip(mapping, lanes, reviews)):
        identity = frame.get('carla_frame'), frame.get('time_s')
        if (frame.get('video_frame') != index or
                (lane.get('frame'), lane.get('time_s')) != identity or
                (review.get('frame'), review.get('time_s')) != identity):
            raise ValueError('Turn-lane original frame identity differs')
        if review.get('source_video_sha256') != video_sha:
            raise ValueError('Stale turn-lane pixel review')
        visible = review.get('visible_turn_lane_designation')
        if visible is not None and type(visible) is not bool:
            raise ValueError('Invalid turn-lane review')
        if visible is True:
            visible_frames.append(frame['carla_frame'])
    return {'lane_ids': sorted(set(row['lane_id'] for row in lanes)),
            'road_ids': sorted(set(row['road_id'] for row in lanes)),
            'visible_designation_frames': visible_frames,
            'designation_review_complete': all(row['visible_turn_lane_designation'] is not None for row in reviews),
            'designated_turn_lane_confirmed': None,
            'legal_signal_exception_judgment': None,
            'sources': {name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}}
