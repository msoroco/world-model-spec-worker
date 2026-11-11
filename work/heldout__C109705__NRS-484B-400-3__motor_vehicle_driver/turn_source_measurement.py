"""Original-frame measurements for a two-directional to one-way left turn.

The source packet records surveyed road geometry and three maneuver intervals.
This module joins every original body footprint to the frame map and reports
descriptive positions. It does not decide statutory practicability.
"""

from hashlib import sha256
import json
from pathlib import Path

from turn_geometry import measure_turn_position


PHASES = ('approach', 'entry', 'departure')
SOURCE_FILES = ('turn_road_geometry.json', 'body_footprints.jsonl',
                'video_frames.jsonl')


def _load_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Original source has no rows: ' + path.name)
    return rows


def measure(source_dir, case_id):
    root = Path(source_dir)
    files = {name: root / name for name in SOURCE_FILES}
    for name, path in files.items():
        if not path.is_file():
            raise ValueError('Missing original turn source: ' + name)
    geometry = json.loads(files['turn_road_geometry.json'].read_text())
    if geometry.get('case_id') != case_id:
        raise ValueError('Turn geometry case identity differs')
    if (geometry.get('approach_directions') != 2
            or geometry.get('destination_directions') != 1
            or geometry.get('maneuver') != 'left_turn'
            or geometry.get('intersection_kind') != 'public_highway_non_alley'):
        raise ValueError('Required highway directions or intersection source is missing')
    frames = _load_rows(files['video_frames.jsonl'])
    footprints = _load_rows(files['body_footprints.jsonl'])
    if len(frames) != len(footprints):
        raise ValueError('Original body and frame-map lengths differ')
    phases = []
    seen = set()
    for index, (frame, body) in enumerate(zip(frames, footprints)):
        if (frame.get('video_frame') != index or frame.get('carla_frame') != body.get('frame')
                or frame.get('time_s') != body.get('time_s')):
            raise ValueError('Original body/frame/time join differs')
        if body.get('actor_id') != geometry.get('ego_actor_id'):
            raise ValueError('Measured body actor identity differs')
        phase = body.get('phase')
        if phase not in PHASES:
            raise ValueError('Original turn phase missing')
        seen.add(phase)
        phases.append(phase)
    if seen != set(PHASES) or phases != sorted(phases, key=PHASES.index):
        raise ValueError('Approach, entry and departure intervals are incomplete or out of order')
    observations = []
    for frame, body in zip(frames, footprints):
        measured = measure_turn_position(
            body['body_corners_xy_m'],
            approach_centerline=geometry['approach_centerline_xy_m'],
            destination_left_curb=geometry['destination_left_curb_xy_m'],
            intersection_entry=geometry['intersection_entry_xy_m'])
        observations.append({'frame': frame['carla_frame'], 'time_s': frame['time_s'],
                             'phase': body['phase'], **measured})
    approach = [row for row in observations if row['phase'] == 'approach']
    entry = [row for row in observations if row['phase'] == 'entry']
    departure = [row for row in observations if row['phase'] == 'departure']
    return {'case_id': case_id, 'frame_count': len(frames),
            'source_sha256': {name: sha256(path.read_bytes()).hexdigest()
                              for name, path in files.items()},
            'approach_all_original_corners_right_of_centerline': all(
                row['approach_all_corners_right_of_centerline'] for row in approach + entry),
            'approach_nearest_corner_offset_m': min(
                abs(offset) for row in approach for offset in row['approach_signed_corner_offsets_m']),
            'entry_all_original_corners_right_of_centerline': all(
                row['approach_all_corners_right_of_centerline'] for row in entry),
            'departure_min_original_corner_to_left_curb_m': min(
                distance for row in departure for distance in row['destination_curb_corner_distances_m']),
            'observations': observations,
            'legal_practicability_decided': False}
