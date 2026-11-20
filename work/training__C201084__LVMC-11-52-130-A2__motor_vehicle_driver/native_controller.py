"""Source-driven attempted destination stop for the two fire-lane cases."""
from math import atan2, degrees, hypot, isfinite, sqrt


def command(position_xy, yaw_deg, velocity_xyz_mps, target_xy,
            *, stop_radius_m=0.8, cruise_mps=4.0, deceleration_mps2=2.0):
    values = (*position_xy, yaw_deg, *velocity_xyz_mps, *target_xy,
              stop_radius_m, cruise_mps, deceleration_mps2)
    if any(type(value) not in (int, float) or not isfinite(value)
           for value in values):
        raise ValueError('Stop controller needs finite original pose, velocity and target')
    if min(stop_radius_m, cruise_mps, deceleration_mps2) <= 0:
        raise ValueError('Stop controller tuning must be positive')
    dx, dy = target_xy[0]-position_xy[0], target_xy[1]-position_xy[1]
    distance = hypot(dx, dy)
    speed = hypot(hypot(*velocity_xyz_mps[:2]), velocity_xyz_mps[2])
    if distance <= stop_radius_m:
        return {'throttle': 0.0, 'brake': 1.0, 'steer': 0.0,
                'hand_brake': speed <= 0.05, 'phase': 'target_braking',
                'distance_to_target_m': distance, 'source_speed_mps': speed}
    desired = min(cruise_mps, sqrt(max(0.0, 2*deceleration_mps2*
                                      (distance-stop_radius_m))))
    error = (degrees(atan2(dy, dx))-yaw_deg+180)%360-180
    steer = max(-0.65, min(0.65, error/45))
    return {'throttle': max(0.0, min(0.55, 0.2+0.2*(desired-speed))),
            'brake': max(0.0, min(1.0, (speed-desired)/deceleration_mps2)),
            'steer': steer, 'hand_brake': False,
            'phase': 'approach', 'distance_to_target_m': distance,
            'source_speed_mps': speed}


def apply(ego, carla, target_xy, **tuning):
    transform = ego.get_transform()
    location = transform.location
    velocity = ego.get_velocity()
    observed = command([location.x, location.y], transform.rotation.yaw,
                       [velocity.x, velocity.y, velocity.z], target_xy, **tuning)
    ego.apply_control(carla.VehicleControl(**{key: observed[key] for key in
        ('throttle', 'brake', 'steer', 'hand_brake')}))
    return observed
