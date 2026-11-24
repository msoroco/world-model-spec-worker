"""Original Native body footprints and pairwise planar clearances.

The caller supplies actor transforms and bounding boxes from the same Native
frame. A zero planar separation is an overlap cue, not a collision verdict.
"""
import math


def require_finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Nonfinite Native body geometry')
    return float(value)


def footprint(actor):
    box = actor.bounding_box
    ext = box.extent
    if require_finite(ext.x) <= 0 or require_finite(ext.y) <= 0:
        raise ValueError('Native body box has no planar extent')
    pose = actor.get_transform()
    points = []
    for x, y in ((-ext.x, -ext.y), (ext.x, -ext.y),
                 (ext.x, ext.y), (-ext.x, ext.y)):
        local = type(box.location)(x=box.location.x + x,
                                   y=box.location.y + y,
                                   z=box.location.z)
        point = pose.transform(local)
        points.append([require_finite(point.x), require_finite(point.y)])
    return points


def _axes(polygon):
    for first, second in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = second[0] - first[0], second[1] - first[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            raise ValueError('Degenerate Native body footprint')
        yield (-dy / length, dx / length)


def _overlap(left, right):
    for ax, ay in list(_axes(left)) + list(_axes(right)):
        a = [x * ax + y * ay for x, y in left]
        b = [x * ax + y * ay for x, y in right]
        if max(a) < min(b) or max(b) < min(a):
            return False
    return True


def _point_segment_distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    if length2 <= 0:
        raise ValueError('Degenerate Native body edge')
    t = max(0.0, min(1.0, ((point[0] - start[0]) * dx +
                            (point[1] - start[1]) * dy) / length2))
    return math.hypot(point[0] - start[0] - t * dx,
                      point[1] - start[1] - t * dy)


def planar_gap(left, right):
    if type(left) is not list or type(right) is not list or len(left) != 4 or len(right) != 4:
        raise ValueError('Four original Native body corners required')
    for polygon in (left, right):
        for point in polygon:
            if len(point) != 2:
                raise ValueError('Invalid Native body corner')
            for value in point:
                require_finite(value)
    if _overlap(left, right):
        return 0.0
    return min(_point_segment_distance(point, a, b)
               for polygon, opposite in ((left, right), (right, left))
               for point in polygon
               for a, b in zip(opposite, opposite[1:] + opposite[:1]))


def constant_velocity_time_to_overlap(left, left_velocity, right,
                                      right_velocity, horizon_s=30):
    """Predicted planar body overlap from same-frame Native velocities.

    This is a kinematic proxy, not an observed collision or legal threshold.
    """
    planar_gap(left, right)
    if (type(left_velocity) is not list or type(right_velocity) is not list or
            len(left_velocity) != 2 or len(right_velocity) != 2):
        raise ValueError('Original Native planar body velocities required')
    for value in left_velocity + right_velocity:
        require_finite(value)
    require_finite(horizon_s)
    if horizon_s <= 0:
        raise ValueError('Positive prediction horizon required')
    relative = [right_velocity[i] - left_velocity[i] for i in (0, 1)]
    entering, leaving = 0.0, float(horizon_s)
    for ax, ay in list(_axes(left)) + list(_axes(right)):
        a = [x * ax + y * ay for x, y in left]
        b = [x * ax + y * ay for x, y in right]
        delta = relative[0] * ax + relative[1] * ay
        if abs(delta) < 1e-12:
            if max(a) < min(b) or max(b) < min(a):
                return None
            continue
        bounds = sorted(((min(a) - max(b)) / delta,
                         (max(a) - min(b)) / delta))
        entering = max(entering, bounds[0])
        leaving = min(leaving, bounds[1])
        if entering > leaving:
            return None
    return max(0.0, entering) if entering <= leaving else None


def scene_clearance(ego, participants):
    own = footprint(ego)
    ego_velocity = ego.get_velocity()
    own_velocity = [require_finite(ego_velocity.x), require_finite(ego_velocity.y)]
    bodies = []
    for actor in participants:
        if actor.id == ego.id:
            continue
        if not (actor.type_id.startswith('vehicle.') or
                actor.type_id.startswith('walker.')):
            continue
        points = footprint(actor)
        velocity = actor.get_velocity()
        participant_velocity = [require_finite(velocity.x), require_finite(velocity.y)]
        bodies.append({'actor_id': int(actor.id), 'type_id': actor.type_id,
                       'footprint_xy_m': points,
                       'velocity_xy_mps': participant_velocity,
                       'planar_gap_m': planar_gap(own, points),
                       'constant_velocity_time_to_overlap_s':
                           constant_velocity_time_to_overlap(
                               own, own_velocity, points, participant_velocity)})
    bodies.sort(key=lambda item: item['actor_id'])
    return {'ego_footprint_xy_m': own, 'ego_velocity_xy_mps': own_velocity,
            'participants': bodies,
            'minimum_surface_gap_m': min((item['planar_gap_m'] for item in bodies),
                                         default=None),
            'minimum_constant_velocity_time_to_overlap_s':
                min((item['constant_velocity_time_to_overlap_s'] for item in bodies
                     if item['constant_velocity_time_to_overlap_s'] is not None),
                    default=None),
            'gap_method': 'original_native_2d_body_footprint_separation',
            'limitation': 'Planar body gap is not a three-dimensional contact or legal judgment.'}


def curbside_lane_info(native_map, location, driving_type, curb_types):
    """Require a source-observed driving lane with a physical roadside neighbor."""
    lane = native_map.get_waypoint(location, project_to_road=False,
                                   lane_type=driving_type)
    if lane is None or lane.lane_type != driving_type:
        raise ValueError('Spawn lacks original Native driving-lane waypoint')
    curb_neighbor = lane.get_right_lane()
    if curb_neighbor is None or curb_neighbor.lane_type not in curb_types:
        raise ValueError('Spawn lacks original Native curbside neighbor')
    return {'road_id': int(lane.road_id), 'section_id': int(lane.section_id),
            'lane_id': int(lane.lane_id),
            'right_neighbor_road_id': int(curb_neighbor.road_id),
            'right_neighbor_lane_id': int(curb_neighbor.lane_id),
            'right_neighbor_type': str(curb_neighbor.lane_type),
            'method': 'native_waypoint_right_lane_source',
            'limitation': 'Adjacent lane topology identifies a curbside candidate; actual curb geometry and municipal jurisdiction require review.'}


def choose_curbside_spawn(native_map, spawns, preferred_index, driving_type, curb_types):
    if type(preferred_index) is not int or preferred_index < 0 or preferred_index >= len(spawns):
        raise ValueError('Preferred Native spawn index unavailable')
    order = [preferred_index] + [index for index in range(len(spawns))
                                 if index != preferred_index]
    for index in order:
        try:
            info = curbside_lane_info(native_map, spawns[index].location,
                                      driving_type, curb_types)
        except ValueError:
            continue
        return index, info
    raise ValueError('No source-observed curbside driving spawn exists in Native map')


def spawn_sidewalk_pedestrian(world, roadside_lane, selector):
    if selector != 'walker.pedestrian.*' or roadside_lane is None:
        raise ValueError('Exact adjacent-sidewalk pedestrian construction required')
    walkers = sorted(world.get_blueprint_library().filter(selector),
                     key=lambda blueprint: blueprint.id)
    if not walkers:
        raise RuntimeError('No Native pedestrian blueprint available')
    pose = roadside_lane.transform
    pose.location.z += 0.3
    walker = world.try_spawn_actor(walkers[0], pose)
    if walker is None:
        raise RuntimeError('Adjacent sidewalk pedestrian spawn unavailable')
    return walker
