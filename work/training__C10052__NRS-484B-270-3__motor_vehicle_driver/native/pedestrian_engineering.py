"""Source-bound CPU construction for the cross-referenced pedestrian condition.

All coordinates and observations here are synthetic proposals. The measurements
do not establish an original Native sidewalk, obstruction, or right of way.
"""
from __future__ import annotations

from rider_candidates import NAMES, parameters as rider_parameters
from rider_engineering import CONFLICT_BOUNDS_M, ego_pose
from measure_facility import overlap_area

SIDEWALK_Y_M = -7.0
LANE_Y_M = -4.0
OBSTRUCTION_X_M = (-6.0, 6.0)
BUFFER_X_M = (-6.0, 6.0)
FRAMES = 480


def construction(response: str, candidate: str) -> dict:
    if response not in ('clear', 'conflict') or candidate not in NAMES:
        raise ValueError('Unknown pedestrian case/candidate')
    rider = rider_parameters('bicycle', response, candidate)
    return {
        'case_suffix': 'pedestrian_' + response,
        'candidate_id': candidate,
        'response': response,
        'approach_start_x_m': rider['approach_start_x_m'],
        'release_shift_frames': rider['release_shift_frames'],
        'reference_camera_xyz_m': rider['reference_camera_xyz_m'],
        'sidewalk_y_m': SIDEWALK_Y_M,
        'bicycle_lane_y_m': LANE_Y_M,
        'obstruction_x_m': list(OBSTRUCTION_X_M),
        'impassable_buffer_x_m': list(BUFFER_X_M),
        'capture_frames': FRAMES,
        'source_kind': 'synthetic_cpu_fixture',
        'accepted': False,
    }


def pedestrian_pose(frame: int, *, blocked=True, return_delay=0) -> dict:
    if type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError('Invalid frame')
    if type(return_delay) is not int or not 0 <= return_delay <= 30:
        raise ValueError('Invalid return delay')
    x = -20.0 + .2 * max(0, min(frame - 100, 200))
    if not blocked:
        y = SIDEWALK_Y_M
    elif frame < 145:
        y = SIDEWALK_Y_M + (LANE_Y_M - SIDEWALK_Y_M) * max(0, frame - 120) / 25
    elif frame <= 240 + return_delay:
        y = LANE_Y_M
    elif frame < 260 + return_delay:
        y = LANE_Y_M + (SIDEWALK_Y_M - LANE_Y_M) * (frame - 240 - return_delay) / 20
    else:
        y = SIDEWALK_Y_M
    return {'center_xy': [round(x, 4), round(y, 4)],
            'body_xy': [[round(x-.3, 4), round(y-.25, 4)],
                        [round(x+.3, 4), round(y-.25, 4)],
                        [round(x+.3, 4), round(y+.25, 4)],
                        [round(x-.3, 4), round(y+.25, 4)]]}


def measure(rows: list[dict], construction_data: dict) -> dict:
    if len(rows) != FRAMES or construction_data['capture_frames'] != FRAMES:
        raise ValueError('Expected 480 saved rows')
    if any(row['native_frame'] != 1000+i or row['time_s'] != round(i/20, 2)
           for i, row in enumerate(rows)):
        raise ValueError('Frame/time join changed')
    sidewalk_obstructed = all(row['sidewalk_obstructed'] is True
                               for row in rows if OBSTRUCTION_X_M[0] <= row['pedestrian_xy'][0] <= OBSTRUCTION_X_M[1])
    buffer_impassable = all(row['buffer_impassable'] is True
                            for row in rows if BUFFER_X_M[0] <= row['pedestrian_xy'][0] <= BUFFER_X_M[1])
    lane = [i for i, row in enumerate(rows)
            if overlap_area(row['pedestrian_body_xy'], CONFLICT_BOUNDS_M) > .01]
    ego = [i for i, row in enumerate(rows)
           if overlap_area(row['ego_body_xy'], CONFLICT_BOUNDS_M) > .01]
    simultaneous = sorted(set(lane) & set(ego))
    x_values = [row['pedestrian_xy'][0] for row in rows]
    y_values = [row['pedestrian_xy'][1] for row in rows]
    path_control = (all(b >= a for a, b in zip(x_values, x_values[1:])) and
                    all(abs(b-a) <= .21 for a, b in zip(x_values, x_values[1:])) and
                    all(-7.01 <= y <= -3.99 for y in y_values))
    return_frame = next((i for i in range(241, FRAMES)
                         if rows[i]['pedestrian_xy'][1] == SIDEWALK_Y_M), None)
    # The scripted path reaches the far edge of the obstacle at frame 230.
    return_gap = None if return_frame is None else return_frame - 230
    qualifying_geometry = (sidewalk_obstructed and buffer_impassable and path_control and
                           bool(lane) and return_gap is not None and return_gap <= 30)
    return {'case_suffix': construction_data['case_suffix'],
            'candidate_id': construction_data['candidate_id'],
            'sidewalk_obstructed': sidewalk_obstructed,
            'buffer_impassable': buffer_impassable,
            'bounded_monotonic_path': path_control,
            'first_pedestrian_conflict_frame': lane[0] if lane else None,
            'last_pedestrian_conflict_frame': lane[-1] if lane else None,
            'first_ego_conflict_frame': ego[0] if ego else None,
            'simultaneous_conflict_frames': len(simultaneous),
            'first_sidewalk_return_frame': return_frame,
            'return_gap_after_obstacle_frames': return_gap,
            'qualifying_synthetic_geometry': qualifying_geometry,
            'original_native_verified': False, 'legal_yield_finding': None,
            'accepted': False}


def fixture_rows(response: str, candidate: str, *, blocked=True, return_delay=0) -> list[dict]:
    p = construction(response, candidate)
    rows = []
    for i in range(FRAMES):
        pedestrian = pedestrian_pose(i, blocked=blocked, return_delay=return_delay)
        ego = ego_pose(i, response, p['approach_start_x_m'], p['release_shift_frames'])
        rows.append({'native_frame': 1000+i, 'time_s': round(i/20, 2),
                     'pedestrian_xy': pedestrian['center_xy'],
                     'pedestrian_body_xy': pedestrian['body_xy'],
                     'ego_body_xy': ego['body_xy'],
                     'sidewalk_obstructed': blocked,
                     'buffer_impassable': blocked})
    return rows
