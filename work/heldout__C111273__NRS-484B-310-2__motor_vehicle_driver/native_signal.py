"""Lazy CARLA flashing-yellow source selection and readback controller.

The supplied official-control record is a planning premise. A CARLA traffic
light and its affected lane waypoints establish only simulated lane linkage.
"""
from dataclasses import dataclass
from math import cos, radians, sin


@dataclass(frozen=True)
class Approach:
    light: object
    waypoint: object
    junction_id: int
    direction: str
    opendrive_id: str


def _xy(waypoint):
    p = waypoint.transform.location
    return (float(p.x), float(p.y))


def _direction(waypoint):
    yaw = radians(float(waypoint.transform.rotation.yaw))
    x, y = cos(yaw), sin(yaw)
    if abs(x) < .75 or abs(y) > .66:
        return None
    return 'east' if x > 0 else 'west'


def _junction_id(waypoint):
    """Follow the governed lane toward its first intersection."""
    cursor = waypoint
    for _ in range(16):
        junction = cursor.get_junction()
        if junction is not None:
            return int(junction.id)
        successors = cursor.next(2.0)
        if len(successors) != 1:
            return None
        cursor = successors[0]
    return None


def discover_approaches(lights, official_control_source):
    """Return an east/west pair linked by one simulated junction.

    Require an identified control premise, source OpenDRIVE identifiers, and
    affected lane waypoints. Ambiguous maps fail closed for manual route choice.
    """
    if not official_control_source or not str(official_control_source).strip():
        raise ValueError('missing official-control source premise')
    by_junction = {}
    for light in lights:
        od_id = str(light.get_opendrive_id() or '').strip()
        if not od_id:
            continue
        for waypoint in light.get_affected_lane_waypoints():
            direction = _direction(waypoint)
            junction_id = _junction_id(waypoint)
            if direction is None or junction_id is None:
                continue
            by_junction.setdefault(junction_id, {}).setdefault(direction, []).append(
                Approach(light, waypoint, junction_id, direction, od_id))
    for junction_id in sorted(by_junction):
        sides = by_junction[junction_id]
        if 'east' in sides and 'west' in sides:
            east, west = sides['east'][0], sides['west'][0]
            if east.light.id == west.light.id:
                continue
            return {'east': east, 'west': west}
    raise ValueError('no distinct opposing governed heads at one junction')


def route_for(approach, before_m=70.0, after_m=70.0):
    """Use the governed lane waypoint, not world-origin coordinates."""
    if before_m <= 0 or after_m <= 0:
        raise ValueError('route distances must be positive')
    starts = approach.waypoint.previous(before_m)
    ends = approach.waypoint.next(after_m)
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError('governed lane has ambiguous route')
    start, end = starts[0], ends[0]
    x0, _ = _xy(start)
    x1, _ = _xy(end)
    if (x1 - x0) * (1 if approach.direction == 'east' else -1) <= 0:
        raise ValueError('route does not follow governed approach direction')
    return (start.transform, end.transform)


def crossing_route(world_map, junction_id, sample_step_m=5.0,
                   before_m=65.0, after_m=65.0):
    """Find one perpendicular travel lane that traverses this same junction."""
    candidates = []
    for waypoint in world_map.generate_waypoints(sample_step_m):
        if _junction_id(waypoint) != junction_id:
            continue
        yaw = radians(float(waypoint.transform.rotation.yaw))
        if abs(sin(yaw)) < .75 or abs(cos(yaw)) > .66:
            continue
        starts, ends = waypoint.previous(before_m), waypoint.next(after_m)
        if len(starts) != 1 or len(ends) != 1:
            continue
        x0, y0 = _xy(starts[0]); x1, y1 = _xy(ends[0])
        if abs(y1-y0) < before_m/2:
            continue
        candidates.append((int(waypoint.road_id), int(waypoint.lane_id),
                           starts[0].transform, ends[0].transform))
    if not candidates:
        raise ValueError('no traversing perpendicular crossing lane at selected junction')
    candidates.sort(key=lambda x: (x[0], x[1]))
    road_id, lane_id, start, end = candidates[0]
    return {'road_id': road_id, 'lane_id': lane_id, 'start': start, 'end': end}


def construct_native(world, case, official_control_source, blueprint_id='vehicle.tesla.model3'):
    """Place the selected participants on map governed lanes.

    The caller owns returned vehicle actors and must destroy them in a finally
    block. This function cleans up actors itself if construction fails.
    """
    if case.direction not in ('east', 'west'):
        raise ValueError('unsupported approach direction')
    approaches = discover_approaches(
        world.get_actors().filter('traffic.traffic_light*'), official_control_source)
    selected = approaches[case.direction]
    ego_route = route_for(selected)
    cross_route = (crossing_route(world.get_map(), selected.junction_id)
                   if case.crossing_vehicle else None)
    blueprint = world.get_blueprint_library().find(blueprint_id)
    owned = []
    try:
        ego = world.try_spawn_actor(blueprint, ego_route[0])
        if ego is None:
            raise ValueError('ego Native actor spawn failed')
        owned.append(ego)
        crossing = None
        if cross_route is not None:
            crossing = world.try_spawn_actor(blueprint, cross_route['start'])
            if crossing is None:
                raise ValueError('crossing Native actor spawn failed')
            owned.append(crossing)
        return {'approaches': approaches, 'selected': selected,
                'light': selected.light, 'ego_route': ego_route,
                'crossing_route': cross_route, 'ego': ego,
                'crossing': crossing, 'owned': owned,
                'official_control_source': official_control_source}
    except BaseException:
        for actor in reversed(owned):
            actor.destroy()
        raise


class FlashController:
    """Set and verify an existing Native light state on every capture tick."""
    def __init__(self, light, traffic_light_state, period_s=.5):
        if period_s <= 0:
            raise ValueError('period must be positive')
        self.light = light
        self.state = traffic_light_state
        self.period_s = period_s
        self.initial_state = None

    def __enter__(self):
        self.initial_state = self.light.get_state()
        return self

    def set_at(self, time_s):
        if self.initial_state is None:
            raise RuntimeError('controller not entered')
        if time_s < 0:
            raise ValueError('negative capture time')
        on = (time_s % self.period_s) < self.period_s / 2
        target = self.state.Yellow if on else self.state.Off
        self.light.set_state(target)
        observed = self.light.get_state()
        if observed != target:
            raise ValueError('flashing-yellow Native readback mismatch')
        return {'yellow_commanded': on, 'native_light_state': str(observed),
                'light_actor_id': int(self.light.id)}

    def __exit__(self, exc_type, exc, tb):
        if self.initial_state is not None:
            self.light.set_state(self.initial_state)
            if self.light.get_state() != self.initial_state:
                raise ValueError('traffic-light restoration readback mismatch')
            self.initial_state = None
