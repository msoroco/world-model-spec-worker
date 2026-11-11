"""Choose a connected through-intersection following route from Native waypoints.

The apparatus is placed beyond the junction while the subject starts before it.
This checks authored route geometry only; actual motion and visibility remain unknown.
"""
from math import atan2, cos, hypot, isfinite, sin

FEET_PER_METRE = 3.280839895013123


def _xy(waypoint):
    position = waypoint.transform.location
    return float(position.x), float(position.y)


def _heading(a, b):
    x1, y1 = _xy(a)
    x2, y2 = _xy(b)
    return atan2(y2-y1, x2-x1)


def _turn(previous, current, successor):
    incoming = _heading(previous, current)
    outgoing = _heading(current, successor)
    return abs(atan2(sin(outgoing-incoming), cos(outgoing-incoming)))


def route_from(start, *, target_gap_ft=500, step_m=5, runout_m=35):
    if not isfinite(target_gap_ft) or target_gap_ft <= 0 or step_m <= 0:
        raise ValueError('Invalid intersection route target or sampling step')
    needed = target_gap_ft / FEET_PER_METRE + runout_m
    chain = [start]
    sampled = 0.0
    while sampled < needed + 20:
        current = chain[-1]
        choices = [candidate for candidate in current.next(step_m)
                   if 0.5*step_m <= hypot(_xy(candidate)[0]-_xy(current)[0],
                                          _xy(candidate)[1]-_xy(current)[1]) <= 1.6*step_m]
        if len(chain) == 1:
            choices = [candidate for candidate in choices
                       if candidate.road_id == start.road_id
                       and candidate.lane_id == start.lane_id]
        else:
            choices = [candidate for candidate in choices
                       if _turn(chain[-2], current, candidate) <= 0.55]
        if not choices:
            raise ValueError('No connected through-lane continuation')
        if len(choices) > 1:
            scored = sorted(((_turn(chain[-2], current, candidate), candidate)
                             for candidate in choices), key=lambda item: item[0]) if len(chain) > 1 else None
            if scored is None or scored[1][0] - scored[0][0] < 0.15:
                raise ValueError('Ambiguous intersection continuation')
            selected = scored[0][1]
        else:
            selected = choices[0]
        sampled += hypot(_xy(selected)[0]-_xy(current)[0],
                         _xy(selected)[1]-_xy(current)[1])
        chain.append(selected)
        if len(chain) > 1000:
            raise ValueError('Intersection route sample limit exceeded')
    junction_indices = [index for index, waypoint in enumerate(chain)
                        if waypoint.is_junction]
    if not junction_indices or junction_indices[0] < 3:
        raise ValueError('Following route lacks a junction after the approach')
    if any(b != a+1 for a, b in zip(junction_indices, junction_indices[1:])):
        raise ValueError('Following route traverses multiple separated junctions')
    apparatus_index = next((index for index, waypoint in enumerate(chain)
                            if hypot(_xy(waypoint)[0]-_xy(start)[0],
                                     _xy(waypoint)[1]-_xy(start)[1]) >= target_gap_ft/FEET_PER_METRE), None)
    if apparatus_index is None or junction_indices[-1] >= apparatus_index-2:
        raise ValueError('Apparatus cannot be placed beyond the intersection')
    if any(waypoint.is_junction for waypoint in chain[apparatus_index:]):
        raise ValueError('Apparatus route runout reenters a junction')
    return {'ego': start, 'apparatus': chain[apparatus_index],
            'chain': chain, 'junction_entry': chain[junction_indices[0]],
            'junction_exit': chain[junction_indices[-1]],
            'sampled_distance_m': sampled,
            'centre_separation_m': hypot(_xy(chain[apparatus_index])[0]-_xy(start)[0],
                                         _xy(chain[apparatus_index])[1]-_xy(start)[1])}


def select_intersection_route(world_map, *, target_gap_ft=500, step_m=5):
    failures = []
    for spawn in world_map.get_spawn_points():
        waypoint = world_map.get_waypoint(spawn.location)
        if waypoint is None or waypoint.is_junction:
            continue
        try:
            return route_from(waypoint, target_gap_ft=target_gap_ft, step_m=step_m)
        except ValueError as error:
            failures.append(str(error))
    raise ValueError('No Native through-intersection following route supports the target: '
                     + '; '.join(sorted(set(failures))))
