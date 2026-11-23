"""Lazy Native route policy for four exact C109705 departure settings.

The map survey and source hash must come from an actual reviewed Native map.
No local map or CARLA execution is implied by this CPU-checkable policy.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver'
SUFFIXES = ('near_centerline', 'farther_from_centerline',
            'imaginary_near_centerline', 'imaginary_farther_from_centerline')


def _point(value):
    if not isinstance(value, list) or len(value) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in value):
        raise ValueError('finite map point required')
    return float(value[0]), float(value[1])


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1:
        raise ValueError('degenerate surveyed lane direction')
    return dx / length, dy / length


def _check_road(road):
    if road.get('alley') is not False or road.get('public_highway_source') is None or not road.get('road_id'):
        raise ValueError('sourced non-alley highway identity required')
    lanes = road.get('permitted_lanes')
    if not isinstance(lanes, list) or len(lanes) < 2:
        raise ValueError('opposed permitted lanes missing')
    directions = [_unit(_point(lane['from_xy_m']), _point(lane['to_xy_m'])) for lane in lanes]
    if not any(sum(x * y for x, y in zip(a, b)) < -0.95 for a in directions for b in directions):
        raise ValueError('road is not shown two directional')
    return road['road_id']


def build(case_id, map_survey, *, map_source_path=None):
    if not case_id.startswith(ASSIGNMENT + '__') or case_id.rsplit('__', 1)[1] not in SUFFIXES:
        raise ValueError('case differs from exact assignment')
    suffix = case_id.rsplit('__', 1)[1]
    if map_survey.get('cell_id') != 'C109705' or map_survey.get('maneuver') != 'left_turn':
        raise ValueError('wrong cell or maneuver')
    roads = map_survey.get('intersecting_roads')
    if not isinstance(roads, list) or len(roads) != 2:
        raise ValueError('both intersecting roads required')
    ids = {_check_road(road) for road in roads}
    if {map_survey.get('approach_road_id'), map_survey.get('destination_road_id')} != ids:
        raise ValueError('disconnected approach/destination roads')
    kind = 'source_derived_imaginary' if suffix.startswith('imaginary_') else 'mapped'
    if map_survey.get('destination_centerline_kind') != kind:
        raise ValueError('destination centerline convention differs')
    if kind == 'source_derived_imaginary' and not map_survey.get('imaginary_line_derivation_source'):
        raise ValueError('imaginary line requires source derivation')
    line = map_survey.get('destination_centerline_xy_m')
    if not isinstance(line, list) or len(line) != 2:
        raise ValueError('destination centerline endpoints required')
    a, b = _point(line[0]), _point(line[1])
    direction = _unit(a, b)
    half_width = map_survey.get('destination_half_width_m')
    if type(half_width) not in (float, int) or half_width <= 2.7:
        raise ValueError('destination right half width missing')
    route = map_survey.get('left_turn_route_waypoint_ids')
    if not isinstance(route, list) or len(route) < 3 or not map_survey.get('ego_blueprint_id'):
        raise ValueError('connected left-turn route or vehicle blueprint missing')
    if not map_survey.get('map_name') or not map_survey.get('approach_policy'):
        raise ValueError('map name or fixed approach policy missing')
    if map_survey.get('camera_plan') is None:
        raise ValueError('four-camera plan missing')
    if map_source_path is not None:
        actual = hashlib.sha256(Path(map_source_path).read_bytes()).hexdigest()
        if actual != map_survey.get('source_sha256'):
            raise ValueError('source-hashed Native map differs')
    elif not map_survey.get('source_sha256'):
        raise ValueError('Native map survey hash missing')
    # Distances are engineering targets for the contrast, not statutory cutoffs.
    offset = 1.7 if suffix.endswith('near_centerline') else 2.7
    right = direction[1], -direction[0]
    departure_target = [b[0] + offset * right[0], b[1] + offset * right[1]]
    return {
        'case_id':case_id,
        'map_name':map_survey.get('map_name'),
        'survey_source_sha256':map_survey['source_sha256'],
        'ego_blueprint_id':map_survey['ego_blueprint_id'],
        'left_turn_route_waypoint_ids':route,
        'approach_policy':map_survey.get('approach_policy'),
        'departure_target_xy_m':departure_target,
        'departure_target_offset_m':offset,
        'controller_policy':{'target_speed_mps':7.0,'steer_gain':0.45,'brake_on_route_end':True},
        'camera_plan':map_survey['camera_plan'],
        'duration_s':45,'rate_hz':20,
        'legal_lateral_cutoff':None,
    }


def control(position_xy_m, heading_rad, target_xy_m, speed_mps, *, target_speed_mps=7.0):
    vals = (*position_xy_m, heading_rad, *target_xy_m, speed_mps, target_speed_mps)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in vals):
        raise ValueError('nonfinite control sample')
    if speed_mps < 0 or target_speed_mps <= 0:
        raise ValueError('invalid speed')
    dx, dy = target_xy_m[0] - position_xy_m[0], target_xy_m[1] - position_xy_m[1]
    if math.hypot(dx, dy) < 0.5:
        return {'throttle':0.0,'brake':1.0,'steer':0.0}
    error = (math.atan2(dy, dx) - heading_rad + math.pi) % (2 * math.pi) - math.pi
    return {'throttle':max(0.0,min(0.35,(target_speed_mps - speed_mps) * 0.1)),
            'brake':max(0.0,min(1.0,(speed_mps - target_speed_mps) * 0.2)),
            'steer':max(-1.0,min(1.0,0.45 * error))}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--map-survey', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    path = Path(args.map_survey)
    survey = json.loads(path.read_text())
    source = survey.get('map_source_path')
    if not source:
        raise ValueError('Native map source path missing')
    result = build(args.case, survey, map_source_path=path.parent / source)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
