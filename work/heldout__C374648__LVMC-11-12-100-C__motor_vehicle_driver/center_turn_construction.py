"""Select a source-observable center/outer approach and connected left exit.

Map topology and markings identify a *candidate*.  Designation of a statutory
two-way left-turn lane requires separate authority and original-scene review.
CARLA is deliberately imported only by the eventual Native runner.
"""

from math import atan2, degrees, hypot, isfinite, pi


def _xy(wp):
    loc = wp.transform.location
    point = (float(loc.x), float(loc.y))
    if not all(isfinite(x) for x in point):
        raise ValueError('Nonfinite Native waypoint')
    return point


def _heading(wp):
    vector = wp.transform.get_forward_vector()
    xy = (float(vector.x), float(vector.y))
    if not all(isfinite(x) for x in xy) or hypot(*xy) < .1:
        raise ValueError('Invalid Native waypoint heading')
    return atan2(xy[1], xy[0])


def _driving(wp):
    return wp is not None and 'driving' in str(wp.lane_type).lower()


def _marking(mark):
    return mark is not None and str(mark.type).rsplit('.', 1)[-1].lower() != 'none'


def _marked(wp):
    return _marking(getattr(wp, 'left_lane_marking', None)) and _marking(
        getattr(wp, 'right_lane_marking', None))


def _chain(start, spacing, steps):
    chain = [start]
    for _ in range(steps):
        current = chain[-1]
        successors = [wp for wp in current.next(spacing)
                      if _driving(wp) and _marked(wp) and not wp.is_junction
                      and (wp.road_id, wp.lane_id) == (current.road_id, current.lane_id)]
        if len(successors) != 1:
            raise ValueError('Approach lacks unique marked lane continuation')
        chain.append(successors[0])
    return chain


def _left_exit(last, spacing):
    entry = [wp for wp in last.next(spacing) if _driving(wp) and wp.is_junction]
    choices = []
    for junction in entry:
        for exit_wp in junction.next(8.):
            if not _driving(exit_wp) or exit_wp.is_junction:
                continue
            # CARLA's world y axis points right when heading east.  A left
            # turn therefore rotates clockwise in the xy plane.
            delta = degrees((_heading(exit_wp) - _heading(last) + pi) % (2*pi) - pi)
            if -135 <= delta <= -45:
                choices.append((abs(delta + 90), junction, exit_wp, delta))
    if not choices:
        raise ValueError('No connected observed-heading left exit')
    choices.sort(key=lambda item: item[0])
    return choices[0][1:]


def select_candidate(carla_map, *, spacing_m=2., approach_steps=12,
                     candidate_index=0, direction='east'):
    """Return connected Native waypoints; never certify a statutory designation."""
    if (not isfinite(spacing_m) or spacing_m <= 0 or type(approach_steps) is not int
            or approach_steps < 4 or direction not in ('east', 'west')
            or type(candidate_index) is not int or candidate_index < 0):
        raise ValueError('Invalid center-turn route selection')
    options = []
    for center in carla_map.generate_waypoints(spacing_m):
        if not _driving(center) or center.is_junction or not _marked(center):
            continue
        fx = center.transform.get_forward_vector().x
        if (direction == 'east' and fx < .7) or (direction == 'west' and fx > -.7):
            continue
        outer = center.get_right_lane()
        if (not _driving(outer) or outer.is_junction or not _marked(outer)
                or outer.road_id != center.road_id or outer.lane_id * center.lane_id <= 0):
            continue
        try:
            center_chain = _chain(center, spacing_m, approach_steps)
            outer_chain = _chain(outer, spacing_m, approach_steps)
            junction, exit_wp, delta = _left_exit(center_chain[-1], spacing_m)
            outer_junction, outer_exit, outer_delta = _left_exit(outer_chain[-1], spacing_m)
        except ValueError:
            continue
        if (outer_exit.road_id, outer_exit.lane_id) != (exit_wp.road_id, exit_wp.lane_id):
            continue
        if any((a.road_id != b.road_id or a.lane_id * b.lane_id <= 0
                or hypot(a.transform.location.x-b.transform.location.x,
                         a.transform.location.y-b.transform.location.y) < .5)
               for a, b in zip(center_chain, outer_chain)):
            continue
        options.append((int(center.road_id), int(center.lane_id), *_xy(center), {
            'center_approach': center_chain, 'outer_approach': outer_chain,
            'junction': junction, 'exit': exit_wp,
            'outer_junction': outer_junction, 'outer_exit': outer_exit,
            'center_road_id': int(center.road_id), 'center_lane_id': int(center.lane_id),
            'outer_lane_id': int(outer.lane_id), 'requested_turn_deg': delta,
            'outer_requested_turn_deg': outer_delta,
            'candidate_markings_observed': True, 'designation_authority_verified': False,
        }))
    options.sort(key=lambda item: item[:4])
    if candidate_index >= len(options):
        raise ValueError('No connected marked center/outer left-turn candidate')
    return options[candidate_index][-1]


def route_targets(selection, *, origin='center'):
    if origin not in ('center', 'outer'):
        raise ValueError('Invalid left-turn lane of origin')
    chain = selection['center_approach' if origin == 'center' else 'outer_approach']
    junction = selection['junction' if origin == 'center' else 'outer_junction']
    exit_wp = selection['exit' if origin == 'center' else 'outer_exit']
    return [list(_xy(wp)) for wp in chain] + [list(_xy(junction)), list(_xy(exit_wp))]


def control_step(position_xy, heading_xy, velocity_xy, target_xy, *, target_speed_mps=5.):
    """Feedback for the authored route; observed lane and turn remain separate."""
    dx, dy = target_xy[0]-position_xy[0], target_xy[1]-position_xy[1]
    distance = hypot(dx, dy)
    heading_length = hypot(*heading_xy)
    if distance < .2 or heading_length < 1e-6 or not all(isfinite(v) for v in
            (*position_xy, *heading_xy, *velocity_xy, *target_xy, target_speed_mps)):
        raise ValueError('Invalid Native route feedback state')
    if not 0 < target_speed_mps <= 15:
        raise ValueError('Unsafe requested engineering target speed')
    hx, hy = heading_xy[0]/heading_length, heading_xy[1]/heading_length
    error = atan2(hx*dy-hy*dx, hx*dx+hy*dy)
    speed = hypot(*velocity_xy)
    return {'steer': max(-.5, min(.5, .8*error)),
            'throttle': max(0., min(.45, .22*(target_speed_mps-speed))),
            'brake': max(0., min(.4, .16*(speed-target_speed_mps)))}
