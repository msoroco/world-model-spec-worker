"""Native map and signal binding for the left-arrow crosswalk pair.

CARLA import and capture are deliberately separate. All geometry and source
requirements here can be exercised with a small fake world on a CPU host.
"""
import math

from runner import turn_route


def _distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def connected_turn(start, exit_waypoint, limit=1200):
    target = exit_waypoint.transform.location
    queue = [start]
    visited = set()
    index = 0
    while index < len(queue) and index < limit:
        waypoint = queue[index]
        index += 1
        point = waypoint.transform.location
        identity = (getattr(waypoint, 'road_id', None), getattr(waypoint, 'lane_id', None),
                    round(point.x, 1), round(point.y, 1))
        if identity in visited:
            continue
        visited.add(identity)
        if _distance(point, target) <= 2.5:
            return True
        queue.extend(waypoint.next(2.0))
    return False


def bind_map(world, carla, scene):
    mapping = world.get_map()
    route = turn_route(scene)
    waypoints = []
    for x, y in route:
        target = carla.Location(x=x, y=y, z=0)
        waypoint = mapping.get_waypoint(target)
        if waypoint is None or _distance(waypoint.transform.location, target) > 2:
            raise ValueError('authored left-turn route absent from original Native map')
        waypoints.append(waypoint)
    if not (connected_turn(waypoints[0], waypoints[2]) and
            connected_turn(waypoints[2], waypoints[-1])):
        raise ValueError('original Native map lacks a connected left turn')
    crosswalk_points = mapping.get_crosswalks()
    if not crosswalk_points:
        raise ValueError('original Native map contains no marked adjacent crosswalk')
    left, bottom, right, top = scene['adjacent_crosswalk_bounds_m']
    nearby = [point for point in crosswalk_points
              if left - 2 <= point.x <= right + 2 and bottom - 2 <= point.y <= top + 2]
    if len(nearby) < 4:
        raise ValueError('original marked crosswalk does not match authored adjacent geometry')
    return {'map_source': mapping.name,
            'ego_route_source': 'Native CARLA connected waypoints',
            'adjacent_crosswalk_source': 'Native CARLA map crosswalk vertices',
            'adjacent_crosswalk_bounds_m': scene['adjacent_crosswalk_bounds_m'],
            'route_waypoints': [{'x_m': wp.transform.location.x, 'y_m': wp.transform.location.y,
                                 'road_id': wp.road_id, 'lane_id': wp.lane_id}
                                for wp in waypoints],
            'crosswalk_vertices_m': [[point.x, point.y, point.z] for point in nearby]}


def bind_facing_arrow(ego, scene):
    """Require original signal asset metadata; CARLA Green alone is insufficient."""
    light = ego.get_traffic_light()
    if light is None or light.id != scene['facing_head_id']:
        raise ValueError('authored signal is not the original ego-facing traffic light')
    attributes = light.attributes
    if (attributes.get('signal_shape') != 'arrow' or
            attributes.get('arrow_direction') != scene['arrow_direction'] or
            attributes.get('sole_illuminated') != 'true'):
        raise ValueError('original signal asset does not establish sole left arrow')
    return light


def observed_arrow(light, scene, frame):
    state = str(light.get_state()).split('.')[-1].lower()
    if state != 'green':
        raise ValueError('original ego-facing left arrow is not green in this frame')
    return {'source_verified': True,
            'source_ref': f'Native CARLA traffic light {light.id} asset attributes and state',
            'head_id': light.id, 'observed_frame': frame,
            'illuminated_indications': [{'color': 'green', 'shape': 'arrow',
                                         'direction': scene['arrow_direction']}]}


def spawn_entities(world, scene, vehicle_bp, person_bp, transform):
    """Create distinct ego and pedestrian and destroy partial creations on failure."""
    actors = []
    try:
        ego = world.spawn_actor(vehicle_bp, transform(*scene['ego_start_xy_m'], 0))
        actors.append(ego)
        if scene['crosswalk_setup'] == 'occupied':
            person = world.spawn_actor(person_bp, transform(*scene['pedestrian_start_xy_m'], 0))
            actors.append(person)
        if any(actor is None for actor in actors) or len({a.id for a in actors}) != len(actors):
            raise ValueError('Native ego and pedestrian identities are not distinct')
        return actors
    except BaseException:
        for actor in reversed(actors):
            if actor is not None:
                actor.destroy()
        raise
