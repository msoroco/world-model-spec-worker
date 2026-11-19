"""Source-surveyed route contract for the two C183370 warning-person drafts.

The caller must supply live-map readbacks and two measured route polylines. This
module checks the physical comparison before any CARLA actors are spawned.
"""
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon

CASES = ('reference', 'contrast')
MIN_FRAMES = 600  # 30 s at the requested 20 Hz capture rate.


def _points(value, count):
    if not isinstance(value, list) or len(value) < count:
        raise ValueError('Survey geometry has too few points')
    if any(not isinstance(p, list) or len(p) != 2 or
           any(type(c) not in (int, float) or not math.isfinite(c) for c in p) for p in value):
        raise ValueError('Survey geometry needs numeric XY pairs')
    return value


def validate(survey, live_map_name):
    required = {'map_name', 'road_id', 'repair_polygon_xy_m',
                'warning_person_actor_id', 'warning_person_xy_m',
                'route_over_xy_m', 'route_avoid_xy_m', 'frames',
                'ego_blueprint', 'weather_profile'}
    if not isinstance(survey, dict) or not required <= survey.keys():
        raise ValueError('Missing surveyed warning-person scene facts')
    if survey['map_name'] != live_map_name:
        raise ValueError('Live map differs from source survey')
    if type(survey['road_id']) is not int or type(survey['warning_person_actor_id']) is not int:
        raise ValueError('Road and person need original actor/map identities')
    if type(survey['frames']) is not int or survey['frames'] < MIN_FRAMES:
        raise ValueError('Real capture must last at least 30 seconds at 20 Hz')
    polygon = Polygon(_points(survey['repair_polygon_xy_m'], 3))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Repaired pavement needs a valid measured polygon')
    person = Point(_points([survey['warning_person_xy_m']], 1)[0])
    if person.distance(polygon) > 15:
        raise ValueError('Warning person is not near surveyed pavement')
    over = LineString(_points(survey['route_over_xy_m'], 2))
    avoid = LineString(_points(survey['route_avoid_xy_m'], 2))
    if over.length <= 0 or avoid.length <= 0:
        raise ValueError('Routes need positive measured length')
    if not over.crosses(polygon) or avoid.intersects(polygon):
        raise ValueError('Routes do not isolate passage across repaired pavement')
    if Point(over.coords[0]).distance(Point(avoid.coords[0])) > 0.5 or Point(over.coords[-1]).distance(Point(avoid.coords[-1])) > 0.5:
        raise ValueError('Comparison routes need common surveyed endpoints')
    return {'map_name': live_map_name, 'road_id': survey['road_id'],
            'warning_person_actor_id': survey['warning_person_actor_id'],
            'repair_polygon_xy_m': survey['repair_polygon_xy_m'],
            'frames': survey['frames'], 'capture_rate_hz': 20,
            'ego_blueprint': survey['ego_blueprint'],
            'weather_profile': survey['weather_profile'],
            'cases': {
                'reference': {'route_xy_m': survey['route_over_xy_m'],
                              'requested_pavement_crossing': True},
                'contrast': {'route_xy_m': survey['route_avoid_xy_m'],
                             'requested_pavement_crossing': False}},
            'physical_completion_claimed': False,
            'warning_act_observed': False}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--survey', required=True)
    parser.add_argument('--live-map-name', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    plan = validate(json.loads(Path(args.survey).read_text()), args.live_map_name)
    Path(args.out).write_text(json.dumps(plan, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
