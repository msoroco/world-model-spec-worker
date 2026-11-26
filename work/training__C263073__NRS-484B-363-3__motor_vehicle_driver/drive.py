"""Engineering path follower for a physically simulated school-zone reversal."""
import math

from layout import planned_pose


def command(index, turn, location_xy, yaw_deg, speed_mps):
    """Return steering/throttle/brake; these are motion controls, not legal tests."""
    if index < 0 or index >= 600:
        raise ValueError('Frame outside the 30-second capture')
    target_index = min(index + 12, 599)
    target_x, target_y, _ = planned_pose(target_index, turn)
    dx, dy = target_x - location_xy[0], target_y - location_xy[1]
    distance = math.hypot(dx, dy)
    if not all(math.isfinite(v) for v in (target_x, target_y, yaw_deg, speed_mps, distance)):
        raise ValueError('Nonfinite physical motion input')
    if speed_mps < 0 or speed_mps > 80:
        raise ValueError('Invalid physical speed')
    terminal = index >= (390 if turn else 270) and distance < 2.0
    if terminal:
        return {'steer': 0.0, 'throttle': 0.0, 'brake': 0.7,
                'target_xy_m': [target_x, target_y], 'target_speed_mps': 0.0}
    bearing = math.degrees(math.atan2(dy, dx))
    error = ((bearing - yaw_deg + 180) % 360) - 180
    steer = max(-1.0, min(1.0, error / 35.0))
    target_speed = 2.6 if turn and 95 <= index <= 240 else 3.0
    throttle = max(0.0, min(0.55, 0.25 + 0.2 * (target_speed - speed_mps)))
    brake = max(0.0, min(0.5, 0.25 * (speed_mps - target_speed)))
    return {'steer': steer, 'throttle': throttle, 'brake': brake,
            'target_xy_m': [target_x, target_y], 'target_speed_mps': target_speed}
