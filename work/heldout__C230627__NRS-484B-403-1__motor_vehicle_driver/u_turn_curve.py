"""Native map curve source for the next C230627 centerline U-turn point.

The profile is geometric evidence only. It does not measure a driver's view
of approaching traffic at the 500-foot statutory distance.
"""

from math import acos, degrees, isfinite

from u_turn_construction import _driving, _heading, _opposing, _xy


def curve_profile(approach, *, spacing_m=5.0, samples=6):
    if not (isfinite(spacing_m) and spacing_m > 0 and
            type(samples) is int and samples >= 2):
        raise ValueError('Invalid Native curve sampling')
    current = approach
    points = []
    for index in range(samples + 1):
        x, y = _xy(current)
        heading = _heading(current)
        points.append({'step': index, 'road_id': int(current.road_id),
                       'lane_id': int(current.lane_id),
                       'x_m': x, 'y_m': y,
                       'forward_xy': list(heading)})
        if index == samples:
            break
        choices = [candidate for candidate in current.next(spacing_m)
                   if _driving(candidate) and not candidate.is_junction and
                   int(candidate.road_id) == int(approach.road_id) and
                   int(candidate.lane_id) == int(approach.lane_id)]
        if len(choices) != 1:
            raise ValueError('Native curve profile branch or lane continuity missing')
        current = choices[0]
    a, b = points[0]['forward_xy'], points[-1]['forward_xy']
    dot = max(-1., min(1., a[0]*b[0] + a[1]*b[1]))
    angle = degrees(acos(dot))
    return {'source_kind': 'native_lane_waypoint_profile',
            'sample_spacing_m': spacing_m, 'samples': points,
            'net_heading_change_deg': angle,
            'driver_view_500ft_status': None,
            'approaching_vehicle_visibility_status': None,
            'statutory_407_applicability': None}


def select_curved_u_turn_scene(carla_map, *, waypoint_spacing_m=2.0,
                               candidate_index=0, min_turn_deg=12.0):
    if (not isfinite(waypoint_spacing_m) or waypoint_spacing_m <= 0 or
            not isfinite(min_turn_deg) or min_turn_deg <= 0):
        raise ValueError('Invalid curve scene selection')
    candidates = []
    for approach in carla_map.generate_waypoints(waypoint_spacing_m):
        if not _driving(approach) or approach.is_junction:
            continue
        opposite = _opposing(approach)
        if opposite is None:
            continue
        try:
            profile = curve_profile(approach)
        except ValueError:
            continue
        if profile['net_heading_change_deg'] < min_turn_deg:
            continue
        candidates.append((approach, opposite, profile))
    candidates.sort(key=lambda pair: (int(pair[0].road_id),
                                      int(pair[0].lane_id), *_xy(pair[0])))
    if (type(candidate_index) is not int or candidate_index < 0 or
            candidate_index >= len(candidates)):
        raise ValueError('No requested Native curved opposing-lane U-turn pair')
    approach, opposite, profile = candidates[candidate_index]
    return {'approach': approach, 'opposite': opposite,
            'road_id': int(approach.road_id),
            'approach_lane_id': int(approach.lane_id),
            'opposite_lane_id': int(opposite.lane_id),
            'curve_profile': profile}
