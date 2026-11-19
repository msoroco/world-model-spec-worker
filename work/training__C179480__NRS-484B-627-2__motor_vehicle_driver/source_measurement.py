"""Source-bound motion measurements for roadway-stop analysis.

The inputs are original synchronized per-frame actor samples produced by the
future Native runner. This module reports observations, never a legal verdict.
"""
import json
from math import isfinite
from pathlib import Path


REQUIRED = {'frame', 'ego_speed_mps', 'ego_on_roadway', 'ego_lane_overlap',
            'following_speed_mps', 'following_gap_m'}


def load_rows(path, frame_map_path):
    rows = []
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    with Path(frame_map_path).open(encoding='utf-8') as stream:
        mapping = [json.loads(line) for line in stream if line.strip()]
    if not rows:
        raise ValueError('Missing original actor history')
    if len(rows) != len(mapping):
        raise ValueError('Original actor/frame map length differs')
    previous_frame = -1
    previous_time = float('-inf')
    for index, row in enumerate(rows):
        if not REQUIRED <= set(row):
            raise ValueError('Missing required actor source field')
        frame = mapping[index]
        if (frame.get('video_frame') != index
                or frame.get('carla_frame') != row['frame']
                or row['frame'] <= previous_frame
                or not isinstance(frame.get('time_s'), (int, float))
                or not isfinite(frame['time_s'])
                or frame['time_s'] <= previous_time):
            raise ValueError('Actor frame join is incomplete')
        previous_frame = row['frame']
        previous_time = frame['time_s']
        if type(row['ego_on_roadway']) is not bool or type(row['ego_lane_overlap']) is not bool:
            raise ValueError('Roadway and lane readback must be Boolean')
        for key in ('ego_speed_mps', 'following_speed_mps', 'following_gap_m'):
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                raise ValueError('Invalid original actor measurement: ' + key)
    return rows


def measure(rows, *, fps=20, stop_tolerance_mps=0.05):
    if fps != 20 or not 0 < stop_tolerance_mps <= 0.1:
        raise ValueError('Pinned frame rate or engineering stop tolerance changed')
    if not rows:
        raise ValueError('Missing original actor history')
    stopped = [row for row in rows if row['ego_speed_mps'] <= stop_tolerance_mps]
    roadway_stop = [row for row in stopped if row['ego_on_roadway']]
    overlap_stop = [row for row in roadway_stop if row['ego_lane_overlap']]
    following = [row['following_speed_mps'] for row in rows]
    gaps = [row['following_gap_m'] for row in rows]
    return {
        'sample_count': len(rows),
        'fps': fps,
        'engineering_stop_tolerance_mps': stop_tolerance_mps,
        'complete_stop_observed': bool(stopped),
        'roadway_stop_frames': [row['frame'] for row in roadway_stop],
        'roadway_lane_overlap_frames': [row['frame'] for row in overlap_stop],
        'following_initial_speed_mps': following[0],
        'following_min_speed_mps': min(following),
        'following_speed_drop_mps': max(0.0, following[0] - min(following)),
        'following_min_gap_m': min(gaps),
        'normal_reasonable_movement_impeded': 'independent_original_source_review_required',
        'safe_operation_necessity': 'independent_original_source_review_required',
        'compliance_with_law': 'independent_original_source_review_required',
    }


def analyze(path, frame_map_path):
    return measure(load_rows(path, frame_map_path))


def analyze_hazard(path, frame_map_path, *, source_kind='original_carla_actor_and_map_readback'):
    """Summarize source-visible other-vehicle hazard; do not infer necessity."""
    rows = load_rows(path, frame_map_path)
    gaps = []
    speeds = []
    on_lane = []
    for row in rows:
        state = row.get('hazard_state')
        if not isinstance(state, dict) or state.get('source_kind') != source_kind:
            raise ValueError('Missing original safe-operation hazard state')
        body = state.get('body_vertices_xyz_m')
        velocity = state.get('velocity_xyz_mps')
        position = state.get('position_xyz_m')
        if (not isinstance(body, list) or len(body) < 4
                or any(not isinstance(vertex, list) or len(vertex) != 3
                       or any(type(v) not in (int, float) or not isfinite(v)
                              for v in vertex) for vertex in body)
                or any(not isinstance(vector, list) or len(vector) != 3
                       or any(type(v) not in (int, float) or not isfinite(v)
                              for v in vector) for vector in (velocity, position))
                or type(state.get('on_driving_lane')) is not bool
                or type(state.get('road_id')) is not int
                or type(state.get('lane_id')) is not int):
            raise ValueError('Incomplete original safe-operation hazard geometry')
        for key in ('speed_mps', 'ego_center_gap_m'):
            value = state.get(key)
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError('Invalid original hazard measurement: '+key)
        gaps.append(state['ego_center_gap_m'])
        speeds.append(state['speed_mps'])
        on_lane.append(state['on_driving_lane'])
    return {'sample_count': len(rows), 'minimum_ego_center_gap_m': min(gaps),
            'maximum_hazard_speed_mps': max(speeds),
            'hazard_on_driving_lane_all_frames': all(on_lane),
            'safe_operation_necessity': 'independent_original_source_review_required',
            'physical_causation_claimed': False,
            'legal_verdict_claimed': False}


def analyze_control(path, frame_map_path, *, expected_control_id=None,
                    source_kind='original_carla_actor_and_map_readback'):
    """Retain observed control/ego association without inferring legal compliance."""
    rows = load_rows(path, frame_map_path)
    ids = set()
    associated = []
    red = []
    for row in rows:
        state = row.get('governing_control_state')
        if (not isinstance(state, dict)
                or state.get('source_kind') != source_kind
                or type(state.get('control_actor_id')) is not int
                or state.get('control_type_id') != 'traffic.traffic_light'
                or type(state.get('control_state')) is not str
                or type(state.get('ego_at_control')) is not bool
                or (state.get('ego_associated_control_id') is not None and
                    type(state['ego_associated_control_id']) is not int)):
            raise ValueError('Missing original governing-control readback')
        ids.add(state['control_actor_id'])
        if (expected_control_id is not None and
                state['control_actor_id'] != expected_control_id):
            raise ValueError('Governing control differs from surveyed actor')
        linked = (state['ego_at_control'] and
                  state['ego_associated_control_id'] == state['control_actor_id'])
        if linked:
            associated.append(row['frame'])
            if state['control_state'].split('.')[-1].lower() == 'red':
                red.append(row['frame'])
    if len(ids) != 1:
        raise ValueError('Governing control identity changed during capture')
    return {'sample_count': len(rows), 'control_actor_id': next(iter(ids)),
            'associated_frames': associated, 'associated_red_frames': red,
            'source_visible_stop_requirement': bool(red),
            'compliance_with_law': 'independent_original_source_review_required',
            'legal_verdict_claimed': False}
