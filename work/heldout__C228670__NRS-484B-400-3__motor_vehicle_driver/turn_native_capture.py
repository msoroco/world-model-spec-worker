"""CARLA-lazy original capture of a source-surveyed two-way to one-way left turn."""

import json
from math import hypot
from pathlib import Path
from threading import Condition
from time import monotonic

from turn_native_plan import control_step, seal_route_source, verify_loaded_map
from turn_source_recorder import SourceRecorder


CAMERAS = {
    "overview": ((-8, 0, 8), (-12, 0, 0), (1920, 1080), 95),
    "approach": ((1.2, 0, 2), (0, 0, 0), (1280, 720), 90),
    "reference_corner": ((-3, 2.5, 2.6), (-7, 0, 0), (1280, 720), 100),
    "driver_reference": ((0.6, -0.35, 1.6), (0, 0, 0), (1280, 720), 85),
}


class FourCameraCapture:
    def __init__(self, world, carla_module, ego, on_frame):
        self.condition = Condition()
        self.frames = {name: set() for name in CAMERAS}
        self.errors = []
        self.sensors = []
        self.closed = False
        try:
            for name, (location, rotation, size, fov) in CAMERAS.items():
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                for key, value in (("image_size_x", size[0]), ("image_size_y", size[1]),
                                   ("fov", fov), ("sensor_tick", .05)):
                    blueprint.set_attribute(key, str(value))
                transform = carla_module.Transform(carla_module.Location(*location),
                                                   carla_module.Rotation(*rotation))
                sensor = world.spawn_actor(blueprint, transform, attach_to=ego)
                self.sensors.append(sensor)
                sensor.listen(lambda image, source=name: self._receive(source, image, on_frame))
        except BaseException:
            self.close()
            raise

    def _receive(self, name, image, on_frame):
        with self.condition:
            if self.closed:
                return
            try:
                if image.frame in self.frames[name]:
                    raise ValueError("Duplicate original camera frame")
                if (image.width, image.height) != CAMERAS[name][2]:
                    raise ValueError("Original camera dimensions changed")
                on_frame(name, image)
                self.frames[name].add(image.frame)
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.condition.notify_all()

    def wait_for_frame(self, frame, timeout_s=10):
        deadline = monotonic() + timeout_s
        with self.condition:
            while True:
                if self.errors:
                    raise ValueError("Original camera callback failed") from self.errors[0]
                if all(frame in observed for observed in self.frames.values()):
                    return
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ValueError("Missing original camera frame")
                self.condition.wait(remaining)

    def verify(self, frames):
        expected = set(frames)
        if not expected or any(observed != expected for observed in self.frames.values()):
            raise ValueError("Missing or extra original camera frames")

    def close(self):
        if not self.closed:
            self.closed = True
            for sensor in reversed(self.sensors):
                sensor.stop()
                sensor.destroy()


def _footprint(ego):
    corners = []
    for vertex in ego.bounding_box.get_world_vertices(ego.get_transform()):
        xy = [float(vertex.x), float(vertex.y)]
        if not any(hypot(xy[0]-old[0], xy[1]-old[1]) < 1e-4 for old in corners):
            corners.append(xy)
    if len(corners) != 4:
        raise ValueError("Original Native body footprint incomplete")
    return corners


def _phase(world_map, carla_module, ego, approach_road, departure_road):
    waypoint = world_map.get_waypoint(ego.get_location(), project_to_road=True,
                                      lane_type=carla_module.LaneType.Driving)
    if waypoint is None:
        raise ValueError("Original ego left surveyed driving route")
    if waypoint.is_junction:
        return "entry"
    if waypoint.road_id == approach_road:
        return "approach"
    if waypoint.road_id == departure_road:
        return "departure"
    raise ValueError("Original ego entered an unselected road")


def drive(world, carla_module, ego, plan, route, cameras, recorder, *, frames=160):
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(float(settings.fixed_delta_seconds) - .05) > 1e-6:
        raise ValueError("Original turn capture requires synchronized 20 Hz world")
    targets = plan["targets_xy_m"]
    observed = []
    world_map = world.get_map()

    def record_tick():
        if len(observed) >= frames:
            raise ValueError("Turn exceeded fixed capture duration")
        frame = world.tick()
        cameras.wait_for_frame(frame)
        snapshot = world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("Original Native snapshot frame mismatch")
        recorder.record_body({"frame": frame, "time_s": float(snapshot.timestamp.elapsed_seconds),
                              "phase": _phase(world_map, carla_module, ego, route[0].road_id,
                                              route[-1].road_id),
                              "actor_id": ego.id, "body_corners_xy_m": _footprint(ego)})
        observed.append(frame)

    for target in targets[1:]:
        reached = False
        for _ in range(120):
            transform = ego.get_transform()
            location = transform.location
            position = float(location.x), float(location.y)
            if hypot(target[0]-position[0], target[1]-position[1]) < .8:
                reached = True
                break
            forward = transform.get_forward_vector()
            velocity = ego.get_velocity()
            controls = control_step(position, (float(forward.x), float(forward.y)),
                                    (float(velocity.x), float(velocity.y)), target)
            ego.apply_control(carla_module.VehicleControl(**controls))
            record_tick()
        if not reached:
            location = ego.get_transform().location
            reached = hypot(target[0]-location.x, target[1]-location.y) < .8
        if not reached:
            ego.apply_control(carla_module.VehicleControl(throttle=0., steer=0., brake=1.))
            raise ValueError("Ego did not reach surveyed turn target in tick budget")
    ego.apply_control(carla_module.VehicleControl(throttle=0., steer=0., brake=1.))
    while len(observed) < frames:
        record_tick()
    cameras.verify(observed)
    return {"frames": observed, "targets_reached": len(targets)-1,
            "physical_turn_claimed": False}


def run(plan, output, host="127.0.0.1", port=2000):
    import carla  # Native dependency is intentionally lazy.

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / (name + ".mkv")).exists() for name in CAMERAS):
        raise ValueError("Retain prior Native original cameras")
    client = carla.Client(host, int(port))
    client.set_timeout(30.)
    world = client.get_world()
    world_map = world.get_map()
    route = verify_loaded_map(world_map, plan, carla.LaneType.Driving)
    old_settings = world.get_settings()
    old_sync = old_settings.synchronous_mode
    old_delta = old_settings.fixed_delta_seconds
    ego = None
    recorder = None
    cameras = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        spawn = route[0].transform
        spawn.location.z += .5
        ego = world.try_spawn_actor(world.get_blueprint_library().find("vehicle.tesla.model3"), spawn)
        if ego is None:
            raise ValueError("Native left-turn ego spawn failed")
        recorder = SourceRecorder(output, {name: spec[2] for name, spec in CAMERAS.items()})
        seal_route_source(world_map, plan, carla.LaneType.Driving, output)
        cameras = FourCameraCapture(world, carla, ego, recorder.on_frame)
        outcome = drive(world, carla, ego, plan, route, cameras, recorder)
        recorder.seal()
        (output / "native-turn-result.json").write_text(json.dumps(outcome, indent=2) + "\n")
        return outcome
    finally:
        try:
            if cameras is not None:
                cameras.close()
        finally:
            try:
                if recorder is not None:
                    recorder.close()
            finally:
                try:
                    if ego is not None:
                        ego.destroy()
                finally:
                    old_settings.synchronous_mode = old_sync
                    old_settings.fixed_delta_seconds = old_delta
                    world.apply_settings(old_settings)
