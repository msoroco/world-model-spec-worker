"""CARLA-lazy geometry and controller targets for the C230671 U-turn cell.

These are route requests from Native lane waypoints. Completion, usable road
width, participant behavior and the legal safety judgment require saved sources.
"""

from math import atan2, hypot, isfinite, pi


def _xy(waypoint):
    location = waypoint.transform.location
    return float(location.x), float(location.y)


def _heading(waypoint):
    direction = waypoint.transform.get_forward_vector()
    vector = float(direction.x), float(direction.y)
    length = hypot(*vector)
    if not length or not all(isfinite(x) for x in vector):
        raise ValueError("Native lane heading missing")
    return vector[0] / length, vector[1] / length


def _driving(waypoint):
    return waypoint is not None and 'Driving' in str(waypoint.lane_type)


def _opposing(approach):
    for candidate in (approach.get_left_lane(), approach.get_right_lane()):
        if (not _driving(candidate) or candidate.is_junction or
                int(candidate.road_id) != int(approach.road_id) or
                int(candidate.lane_id) == int(approach.lane_id)):
            continue
        a, b = _heading(approach), _heading(candidate)
        if a[0] * b[0] + a[1] * b[1] < -0.85:
            return candidate
    return None


def select_u_turn_scene(carla_map, *, waypoint_spacing_m=2.0,
                        candidate_index=0):
    """Select a nonjunction road with Native opposite-direction lane evidence.

    A local road-pair check is an engineering screen; prohibitions and actual
    turn space remain source questions. The chosen lane IDs are recorded later.
    """
    if not (isfinite(waypoint_spacing_m) and waypoint_spacing_m > 0):
        raise ValueError("Invalid waypoint spacing")
    candidates = []
    for approach in carla_map.generate_waypoints(waypoint_spacing_m):
        if not _driving(approach) or approach.is_junction:
            continue
        opposite = _opposing(approach)
        if opposite is not None:
            candidates.append((approach, opposite))
    candidates.sort(key=lambda pair: (int(pair[0].road_id), int(pair[0].lane_id),
                                      *_xy(pair[0])))
    if (type(candidate_index) is not int or candidate_index < 0 or
            candidate_index >= len(candidates)):
        raise ValueError("No requested Native opposing-lane U-turn pair")
    approach, opposite = candidates[candidate_index]
    start, end = _xy(approach), _xy(opposite)
    separation = hypot(end[0] - start[0], end[1] - start[1])
    if not isfinite(separation) or separation < 2.0:
        raise ValueError("Opposing Native lane centers too close")
    return {'approach': approach, 'opposite': opposite,
            'road_id': int(approach.road_id),
            'approach_lane_id': int(approach.lane_id),
            'opposite_lane_id': int(opposite.lane_id),
            'lane_center_separation_m': separation}


def select_no_u_turn_device(carla_map, scene, *, max_distance_m=30.0):
    """Require an actual mapped traffic landmark describing a U-turn ban.

    A mapped landmark is source geometry, not itself proof that the device is
    legally official, visible in pixels, or governing this exact lane.
    """
    if not isfinite(max_distance_m) or max_distance_m <= 0:
        raise ValueError('Invalid mapped device distance')
    origin = _xy(scene['approach'])
    matches = []
    for landmark in carla_map.get_all_landmarks():
        if getattr(landmark, 'road_id', None) is None or int(landmark.road_id) != scene['road_id']:
            continue
        fields = [str(getattr(landmark, key, '')) for key in ('name', 'type', 'value')]
        label = ' '.join(fields).lower().replace('-', ' ').replace('_', ' ')
        if not any(marker in label for marker in
                   ('no u turn', 'u turn prohibited', 'u turn forbidden')):
            continue
        transform = getattr(landmark, 'transform', None)
        if transform is None:
            continue
        x, y = float(transform.location.x), float(transform.location.y)
        if not all(isfinite(v) for v in (x, y)):
            continue
        distance = hypot(x-origin[0], y-origin[1])
        if distance <= max_distance_m:
            matches.append((distance, str(landmark.id), landmark, fields))
    if not matches:
        raise ValueError('No source-mapped no-U-turn device near selected lane')
    matches.sort(key=lambda item: (item[0], item[1]))
    distance, _, landmark, fields = matches[0]
    return {'landmark': landmark, 'landmark_id': str(landmark.id),
            'road_id': int(landmark.road_id),
            'distance_to_approach_m': distance,
            'source_fields': dict(zip(('name', 'type', 'value'), fields)),
            'official_device_status': None,
            'governing_lane_status': None,
            'pixel_visibility_status': None}


def verify_incoming_sight_extent(carla_map, scene, route, projector, *, required_m=230.0):
    """Check every planned turn station has both incoming lane routes available.

    This screens route extent for a later per-frame nine-body-ray measurement;
    it does not measure a sight horizon or legal visibility.
    """
    if not isfinite(required_m) or required_m <= 152.4:
        raise ValueError('Sight route extent must exceed the 500 ft probe')
    lane_ids = (scene['approach_lane_id'], scene['opposite_lane_id'])
    checked = []
    for index, point in enumerate(route['targets_xy_m']):
        anchor = projector(float(point[0]), float(point[1]))
        if (anchor is None or int(anchor.road_id) != scene['road_id'] or
                not isfinite(float(anchor.s))):
            raise ValueError('U-turn sight route projection missing at target '+str(index))
        for lane_id in lane_ids:
            lane = carla_map.get_waypoint_xodr(scene['road_id'], lane_id, anchor.s)
            if lane is None or not _driving(lane):
                raise ValueError('U-turn incoming sight lane unavailable at target '+str(index))
            previous = lane.previous(required_m)
            if len(previous) != 1 or previous[0] is None or not _driving(previous[0]):
                raise ValueError('U-turn incoming sight route shorter or ambiguous at target '+str(index))
            checked.append({'target_index': index, 'lane_id': lane_id,
                            'upstream_distance_m': required_m})
    return {'method': 'Native upstream route availability at each planned target',
            'checked': checked, 'sight_horizon_measured': False}


def u_turn_targets(scene, *, arc_extension_m=6.0, samples=24):
    """Request a forward-entry, reverse-heading cubic arc between lane centers."""
    if (not isfinite(arc_extension_m) or arc_extension_m <= 0 or
            type(samples) is not int or samples < 4):
        raise ValueError("Invalid U-turn arc construction")
    start, end = _xy(scene['approach']), _xy(scene['opposite'])
    a, b = _heading(scene['approach']), _heading(scene['opposite'])
    controls = (start,
                (start[0] + arc_extension_m * a[0],
                 start[1] + arc_extension_m * a[1]),
                (end[0] - arc_extension_m * b[0],
                 end[1] - arc_extension_m * b[1]), end)
    points = []
    for index in range(samples + 1):
        t = index / samples
        weights = ((1-t)**3, 3*(1-t)**2*t, 3*(1-t)*t*t, t**3)
        points.append([sum(w*p[0] for w,p in zip(weights, controls)),
                       sum(w*p[1] for w,p in zip(weights, controls))])
    return {'targets_xy_m': points, 'control_points_xy_m': [list(x) for x in controls],
            'requested_arc_extension_m': arc_extension_m,
            'requested_heading_reversal_deg': 180.0}


def participant_placement(scene, *, oncoming_distance_m=24.0,
                          following_distance_m=18.0):
    """Request two distinct traffic roles from original lane headings.

    Native spawn/readback and role/source citations must be retained by capture.
    Distances are engineering knobs, not safe-turn thresholds.
    """
    if any(not isfinite(x) or x <= 0 for x in
           (oncoming_distance_m, following_distance_m)):
        raise ValueError("Invalid participant placement")
    opposite, approach = scene['opposite'], scene['approach']
    ox, oy = _xy(opposite)
    ax, ay = _xy(approach)
    odx, ody = _heading(opposite)
    adx, ady = _heading(approach)
    return {'oncoming': [ox - oncoming_distance_m*odx,
                           oy - oncoming_distance_m*ody],
            'following': [ax - following_distance_m*adx,
                          ay - following_distance_m*ady]}


def control_step(position_xy, forward_xy, velocity_xy, target_xy,
                 *, target_speed_mps=5.0, heading_gain=1.4, speed_gain=.25):
    """Return a bounded steering/speed request from current Native readbacks."""
    points = [tuple(float(v) for v in pair) for pair in
              (position_xy, forward_xy, velocity_xy, target_xy)]
    if any(len(p) != 2 or not all(isfinite(v) for v in p) for p in points):
        raise ValueError('Invalid U-turn controller readback')
    position, forward, velocity, target = points
    if (hypot(*forward) <= 0 or hypot(target[0]-position[0], target[1]-position[1]) <= 0 or
            not all(isfinite(v) and v > 0 for v in
                    (target_speed_mps, heading_gain, speed_gain))):
        raise ValueError('U-turn heading, target or gains invalid')
    bearing = atan2(target[1]-position[1], target[0]-position[0])
    heading = atan2(forward[1], forward[0])
    error = (bearing-heading+pi) % (2*pi)-pi
    steer = max(-1.0, min(1.0, heading_gain*error/(pi/2)))
    speed_error = target_speed_mps-hypot(*velocity)
    return {'steer': steer,
            'throttle': max(0.0, min(1.0, speed_gain*speed_error)),
            'brake': max(0.0, min(1.0, -speed_gain*speed_error))}
