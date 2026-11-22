"""CPU-checkable hill-crest following construction and controller primitives.

Native capture must supply map waypoints and original actor measurements. Targets
are engineering setpoints for a judgment sweep, never statutory cutoffs.
"""
import math


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    return float(value)


def validate_hill_route(samples):
    """Check a connected same-lane approach, crest, and outgoing lane option."""
    if not isinstance(samples, list) or len(samples) < 7:
        raise ValueError('hill approach route needs at least seven Native waypoints')
    road = samples[0]['road_id']
    lane = samples[0]['lane_id']
    if not all(p.get('road_id') == road and p.get('lane_id') == lane and
               p.get('lane_type') == 'Driving' for p in samples):
        raise ValueError('following route must stay on one driving lane')
    stations = [_number(p['station_m'], 'route station') for p in samples]
    heights = [_number(p['z_m'], 'waypoint elevation') for p in samples]
    if any(b-a <= 0 or b-a > 5.0 for a, b in zip(stations, stations[1:])):
        raise ValueError('Native route is disconnected or reversed')
    peak = max(range(2, len(samples)-2), key=lambda i: heights[i])
    if heights[peak]-heights[0] < 1.0 or heights[peak]-heights[-1] < .5:
        raise ValueError('no measured hill crest on selected route')
    if not (stations[peak]-stations[0] >= 12 and stations[-1]-stations[peak] >= 12):
        raise ValueError('insufficient following approach or lane-change exit')
    neighbor = samples[-2].get('adjacent_lane')
    if not isinstance(neighbor, dict) or neighbor.get('road_id') != road or neighbor.get('lane_type') != 'Driving':
        raise ValueError('same-road adjacent driving lane missing')
    if neighbor.get('lane_id') == lane or neighbor.get('forward_dot', 0) < .8:
        raise ValueError('adjacent lane is not a forward lane-change target')
    return {'crest_station_m': stations[peak], 'crest_z_m': heights[peak],
            'following_lane_id': lane, 'target_lane_id': neighbor['lane_id'],
            'road_id': road}


def speed_command(actual_speed_mps, target_speed_mps, gap_m, target_gap_m, relative_speed_mps):
    """Bounded throttle/brake for a requested gap, with closing-rate damping."""
    actual = _number(actual_speed_mps, 'actual speed')
    target = _number(target_speed_mps, 'target speed')
    gap = _number(gap_m, 'original body gap')
    desired = _number(target_gap_m, 'requested body gap')
    closing = _number(relative_speed_mps, 'relative speed')
    if min(actual, target, desired) < 0:
        raise ValueError('negative speed or requested gap')
    error = min(target-actual, .30*(gap-desired)-.8*closing)
    return {'throttle': max(0., min(.6, .22*error)),
            'brake': max(0., min(.8, -.35*error))}


def lane_change_phase(time_s, first_change_s, original_lane_id, observed_lane_id):
    """Gate the post-following maneuver using observed lane identity."""
    t = _number(time_s, 'original time')
    start = _number(first_change_s, 'lane-change start')
    if start <= 20:
        raise ValueError('steady 14..20s following window must precede lane change')
    if t < start:
        if observed_lane_id != original_lane_id:
            raise ValueError('lane changed during following window')
        return 'following'
    return 'changing' if observed_lane_id == original_lane_id else 'changed'
