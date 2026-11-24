"""Observed-pose control plan for the staged signed right/left branches.

The authored route is a controller request. It is never an observed Native
trajectory or evidence that an official sign was present.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from controller import PathController
from geometry import CELLS, FRAMES, RATE_HZ, TURN_FIRST_FRAME


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_plan(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    direction, behavior = config['direction'], config['behavior']
    if direction not in CELLS or behavior not in ('obey', 'turn'):
        raise ValueError('Unknown staged turn identity')
    cell, maneuver, sign, _ = CELLS[direction]
    if (config['cell_id'], config['maneuver'], config['sign_code']) != (cell, maneuver, sign):
        raise ValueError('Frozen cell or prohibition differs')
    if (config['rate_hz'], config['duration_s']) != (RATE_HZ, FRAMES // RATE_HZ):
        raise ValueError('Staged Native timebase differs')
    route_path = root / 'source.jsonl'
    road_path = root / 'road.xodr'
    if sha(route_path) != config['source_sha256'] or sha(road_path) != config['road_sha256']:
        raise ValueError('Staged Native source hash differs')
    rows = [json.loads(line) for line in route_path.read_text().splitlines()]
    if len(rows) != FRAMES or [r['frame'] for r in rows] != list(range(FRAMES)):
        raise ValueError('Staged Native route frame sequence differs')
    for row in rows:
        if row['time_s'] != row['frame'] / RATE_HZ or row['cell_id'] != cell or row['sign_code'] != sign:
            raise ValueError('Staged Native route source identity differs')
    route = [r['body_center_xy_m'] for r in rows]
    if route[TURN_FIRST_FRAME] != [0, -8] or any(
            not 0 < math.dist(a, b) < .2 for a, b in zip(route, route[1:])):
        raise ValueError('Staged Native route discontinuity')
    if behavior == 'turn' and route[-1][0] * (1 if direction == 'right' else -1) <= 8:
        raise ValueError('Staged Native turn exit differs')
    if behavior == 'obey' and any(abs(x) > 1e-9 for x, _ in route):
        raise ValueError('Staged Native obey route turns laterally')
    return config, route


def make_controller(root, wheelbase_m, max_steer_deg):
    config, route = load_plan(root)
    controller = PathController(route, wheelbase_m, max_steer_deg,
                                target_speed_mps=2.7, lookahead_m=3.0)
    return config, controller


def command_from_observation(controller, observed_center_xy_m, observed_heading_deg,
                             observed_speed_mps):
    if not isinstance(observed_center_xy_m, (tuple, list)) or len(observed_center_xy_m) != 2:
        raise ValueError('Original Native center required')
    command = controller.step(position_xy_m=observed_center_xy_m,
                              yaw_rad=math.radians(observed_heading_deg),
                              speed_mps=observed_speed_mps, dt_s=1 / RATE_HZ)
    if command['route_error_m'] > 2.5:
        raise ValueError('Original Native rider departed requested lane/route')
    return command


def survey_governed_sign(mapping, carla, config):
    """Require live approach lane and matching authored landmark readback."""
    wp = mapping.get_waypoint(carla.Location(x=0, y=-35, z=.2),
                              project_to_road=False, lane_type=carla.LaneType.Driving)
    if wp is None or wp.road_id != 1 or wp.lane_id != -1 or not 3.3 <= wp.lane_width <= 3.7:
        raise ValueError('Native signed approach lane readback differs')
    forward = wp.transform.get_forward_vector()
    if forward.y < .98 or abs(forward.x) > .2:
        raise ValueError('Native signed approach heading differs')
    target_id = '11400803' if config['direction'] == 'right' else '11400804'
    matches = [landmark for landmark in mapping.get_all_landmarks()
               if str(landmark.id) == target_id]
    if len(matches) != 1 or int(matches[0].road_id) != 1 or abs(float(matches[0].s) - 56) > .5:
        raise ValueError('Native signed-turn landmark readback differs')
    return {'approach_road_id': int(wp.road_id), 'approach_lane_id': int(wp.lane_id),
            'landmark_id': target_id, 'landmark_station_m': float(matches[0].s),
            'official_device_authorization': 'unreviewed',
            'original_pixels': 'unreviewed', 'physical_turn': 'unreviewed'}
