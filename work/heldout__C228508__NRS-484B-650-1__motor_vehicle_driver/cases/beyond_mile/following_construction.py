"""Portable construction primitives for the C228508 road/follow branch.

The schedule requests two distinct closing encounters in one drive. It does not
label either encounter a violation or establish an immediate hazard. Actual
Native paths, speeds, gaps, signs, bodies and cameras must be retained.
"""

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin


@dataclass(frozen=True)
class Phase:
    start_m: float
    end_m: float
    ego_target_mps: float
    lead_target_mps: float
    label: str


PHASES = (
    Phase(0, 180, 22, 18, 'establish_follow'),
    Phase(180, 300, 24, 11, 'first_closing_request'),
    Phase(300, 1950, 22, 18, 'separate_encounters'),
    Phase(1950, 2070, 24, 11, 'second_closing_request'),
    Phase(2070, 2200, 22, 18, 'continue_driving'),
)


def phase_at(station_m, phases=PHASES):
    if station_m < 0:
        raise ValueError('Negative route station')
    for phase in phases:
        if phase.start_m <= station_m < phase.end_m:
            return phase
    raise ValueError('Route station outside construction')


def validate_schedule(phases=PHASES):
    if not phases or phases[0].start_m != 0:
        raise ValueError('Following schedule must start at route origin')
    for left, right in zip(phases, phases[1:]):
        if left.end_m != right.start_m:
            raise ValueError('Following schedule has a gap or overlap')
    if phases[-1].end_m < 1700:
        raise ValueError('Following route must cover the one-mile comparison')
    closings = [phase for phase in phases if 'closing_request' in phase.label]
    if len(closings) == 2 and closings[1].start_m - closings[0].end_m <= 1609.344:
        raise ValueError('Separated following requests must exceed one mile')
    if len(closings) != 2:
        raise ValueError('Two distinct closing requests required')
    if any(phase.ego_target_mps <= 0 or phase.lead_target_mps <= 0
           for phase in phases):
        raise ValueError('Requested traffic must keep driving')
    return True


def _location(waypoint):
    location = waypoint.transform.location
    return float(location.x), float(location.y)


def route_from_waypoints(first, *, length_m=1800, step_m=5):
    """Walk an existing same-lane map route; reject forks and discontinuities.

    The returned points are Native map references, not a claim that a vehicle
    followed them. Junctions and lane changes require a separate construction.
    """
    if length_m < 1700 or step_m <= 0 or step_m > 10:
        raise ValueError('Route length or sampling step invalid')
    route = [first]
    cumulative = [0.0]
    while cumulative[-1] < length_m:
        options = route[-1].next(step_m)
        same = [candidate for candidate in options
                if candidate.road_id == first.road_id and
                candidate.lane_id == first.lane_id and
                not candidate.is_junction]
        if len(same) != 1:
            raise ValueError('No unique continuous same-lane road route')
        waypoint = same[0]
        x0, y0 = _location(route[-1])
        x1, y1 = _location(waypoint)
        segment = hypot(x1 - x0, y1 - y0)
        if segment < step_m * .25 or segment > step_m * 2:
            raise ValueError('Map route has a discontinuous segment')
        route.append(waypoint)
        cumulative.append(cumulative[-1] + segment)
        if len(route) > 10000:
            raise ValueError('Map route walk did not terminate')
    return route, cumulative


def spawn_pair(world, blueprint_library, ego_transform, lead_transform):
    """Create both vehicle bodies and roll back the first if the second fails."""
    blueprint = blueprint_library.find('vehicle.tesla.model3')
    ego = world.try_spawn_actor(blueprint, ego_transform)
    if ego is None:
        raise ValueError('Could not spawn motor-vehicle driver')
    try:
        lead = world.try_spawn_actor(blueprint, lead_transform)
        if lead is None:
            raise ValueError('Could not spawn lead vehicle')
    except BaseException:
        ego.destroy()
        raise
    return ego, lead


def feedback_control(position_xy, yaw_rad, velocity_xy, target_xy,
                     target_speed_mps, *, steering_gain=1.1):
    """Pure-pursuit-like heading and speed feedback; no teleport or fixed actuation."""
    if target_speed_mps < 0:
        raise ValueError('Negative target speed')
    px, py = position_xy
    tx, ty = target_xy
    if hypot(tx - px, ty - py) < .5:
        raise ValueError('Tracking target too close')
    desired = atan2(ty - py, tx - px)
    error = (desired - yaw_rad + pi) % (2 * pi) - pi
    speed = hypot(*velocity_xy)
    steer = max(-1.0, min(1.0, steering_gain * error))
    speed_error = target_speed_mps - speed
    throttle = max(0.0, min(1.0, speed_error * .18))
    brake = max(0.0, min(1.0, -speed_error * .23))
    return {'steer': steer, 'throttle': throttle, 'brake': brake}


def apply_feedback(vehicle, carla, target_xy, target_speed_mps):
    transform = vehicle.get_transform()
    location = transform.location
    velocity = vehicle.get_velocity()
    command = feedback_control(
        (location.x, location.y), transform.rotation.yaw * pi / 180,
        (velocity.x, velocity.y), target_xy, target_speed_mps)
    vehicle.apply_control(carla.VehicleControl(**command))
    return command


def offset_behind(transform, distance_m, carla):
    if distance_m <= 0:
        raise ValueError('Lead offset must be positive')
    angle = transform.rotation.yaw * pi / 180
    origin = transform.location
    location = carla.Location(x=origin.x - distance_m * cos(angle),
                              y=origin.y - distance_m * sin(angle),
                              z=origin.z)
    return carla.Transform(location, transform.rotation)
