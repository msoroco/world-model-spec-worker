"""Low-speed waypoint steering with a stopped direction change."""
import math


def command(position, yaw_deg, speed_mps, target, reverse=False):
    dx, dy = target[0] - position[0], target[1] - position[1]
    distance = math.hypot(dx, dy)
    desired = math.degrees(math.atan2(dy, dx)) + (180 if reverse else 0)
    error = (desired - yaw_deg + 180) % 360 - 180
    steer = max(-0.55, min(0.55, error / 36))
    speed_target = 2.5 if reverse else 4.0
    throttle = max(0., min(.55, .18 * (speed_target - speed_mps)))
    brake = 0.0 if distance > 1.25 else .45
    return {'steer': steer, 'throttle': 0.0 if brake else throttle,
            'brake': brake, 'reverse': reverse, 'target_distance_m': distance,
            'heading_error_deg': error}


def next_index(route, index, position, speed_mps):
    if index >= len(route) - 1:
        return index, False
    point = route[index]
    if math.dist(position[:2], point[:2]) >= 1.25:
        return index, False
    following = route[index + 1]
    if following[3] != point[3] and speed_mps > .15:
        return index, True
    return index + 1, False
