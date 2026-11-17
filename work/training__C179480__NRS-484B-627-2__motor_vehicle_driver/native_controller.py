"""CARLA-facing control components for the C179480 roadway-stop comparison.

Importing this module does not import or connect to CARLA. The local runner must
survey the chosen lane, supply transforms, and retain original telemetry/video.
"""
from dataclasses import dataclass
from math import atan2, degrees, hypot, sqrt


CAMERAS = (
    ('overview', 1920, 1080, 85, (-8.0, 0.0, 24.0), -55.0),
    ('approach', 1280, 720, 90, (-18.0, 0.0, 3.0), -6.0),
    ('reference_corner', 1280, 720, 90, (4.0, 5.0, 3.0), -15.0),
    ('driver_reference', 1280, 720, 90, (0.2, -0.35, 1.6), -4.0),
)


def camera_specs():
    return [dict(name=name, width=width, height=height, fov=fov,
                 offset_m=offset, pitch_deg=pitch, fps=20)
            for name, width, height, fov, offset, pitch in CAMERAS]


def install_cameras(world, blueprints, carla, parent, on_frame):
    """Spawn four original RGB sources; caller owns their lifecycle and encoding."""
    sensors = []
    try:
        for spec in camera_specs():
            blueprint = blueprints.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(spec['width']))
            blueprint.set_attribute('image_size_y', str(spec['height']))
            blueprint.set_attribute('fov', str(spec['fov']))
            blueprint.set_attribute('sensor_tick', '0.05')
            x, y, z = spec['offset_m']
            transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                        carla.Rotation(pitch=spec['pitch_deg']))
            sensor = world.spawn_actor(blueprint, transform, attach_to=parent)
            sensors.append(sensor)
            sensor.listen(lambda frame, name=spec['name']: on_frame(name, frame))
    except Exception:
        for sensor in reversed(sensors):
            sensor.destroy()
        raise
    return sensors


@dataclass(frozen=True)
class StopControl:
    target_x_m: float
    target_y_m: float
    stop_radius_m: float = 0.8
    approach_speed_mps: float = 4.0

    def decide(self, position_x_m, position_y_m, speed_mps, heading_deg):
        distance = hypot(self.target_x_m - position_x_m,
                         self.target_y_m - position_y_m)
        if distance <= self.stop_radius_m:
            return {'throttle': 0.0, 'brake': 1.0, 'steer': 0.0,
                    'target_reached': True}
        desired_speed = min(self.approach_speed_mps,
                            sqrt(2.0 * 2.0 * max(0.0, distance - self.stop_radius_m)))
        bearing = degrees(atan2(self.target_y_m - position_y_m,
                                self.target_x_m - position_x_m))
        heading_error = (bearing - heading_deg + 180.0) % 360.0 - 180.0
        steer = max(-0.45, min(0.45, heading_error / 40.0))
        braking = speed_mps > desired_speed + 0.3
        return {'throttle': 0.0 if braking else 0.32 if speed_mps < desired_speed else 0.0,
                'brake': 0.55 if braking else 0.0, 'steer': steer,
                'target_reached': False}


def apply_stop_control(vehicle, control_type, controller):
    transform = vehicle.get_transform()
    pose = transform.location
    velocity = vehicle.get_velocity()
    speed = hypot(hypot(velocity.x, velocity.y), velocity.z)
    decision = controller.decide(pose.x, pose.y, speed, transform.rotation.yaw)
    vehicle.apply_control(control_type(throttle=decision['throttle'],
                                       brake=decision['brake'],
                                       steer=decision['steer']))
    return {'position_x_m': pose.x, 'position_y_m': pose.y,
            'speed_mps': speed, 'distance_to_stop_m': hypot(
                controller.target_x_m - pose.x, controller.target_y_m - pose.y),
            'command': decision}
