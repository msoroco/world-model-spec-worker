"""CARLA-lazy first exact overtaking capture; no physical success claim."""

import argparse
import hashlib
import json
import os
from math import hypot
from pathlib import Path
from threading import Condition
from time import monotonic

from overtake_native_plan import CASE, control, prepare, verify_loaded_site
from overtake_source_recorder import CAMERAS, SourceRecorder

CAMERA_SETUP = {
    "overview": ((-8., 0., 8.), (-12., 0., 0.), (1920, 1080), 95),
    "approach": ((1.2, 0., 2.), (0., 0., 0.), (1280, 720), 90),
    "reference_corner": ((-3., 2.5, 2.6), (-7., 0., 0.), (1280, 720), 100),
    "driver_reference": ((.6, -.35, 1.6), (0., 0., 0.), (1280, 720), 85),
}


class Cameras:
    def __init__(self, world, carla, ego, on_frame):
        self.condition = Condition()
        self.frames = {name: set() for name in CAMERAS}
        self.errors = []
        self.sensors = []
        self.closed = False
        try:
            for name, (place, angles, size, fov) in CAMERA_SETUP.items():
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                for key, value in (("image_size_x", size[0]), ("image_size_y", size[1]),
                                   ("fov", fov), ("sensor_tick", .05)):
                    blueprint.set_attribute(key, str(value))
                transform = carla.Transform(carla.Location(*place), carla.Rotation(*angles))
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
                if image.frame in self.frames[name] or (image.width, image.height) != CAMERA_SETUP[name][2]:
                    raise ValueError("Original camera frame duplicated or changed size")
                on_frame(name, image)
                self.frames[name].add(image.frame)
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.condition.notify_all()

    def wait(self, frame, timeout_s=10.):
        deadline = monotonic() + timeout_s
        with self.condition:
            while True:
                if self.errors:
                    raise ValueError("Original camera callback failed") from self.errors[0]
                if all(frame in self.frames[name] for name in CAMERAS):
                    return
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ValueError("Missing original camera frame")
                self.condition.wait(remaining)

    def verify(self, frames):
        wanted = set(frames)
        if not wanted or any(observed != wanted for observed in self.frames.values()):
            raise ValueError("Original camera/body frame inventories differ")

    def close(self):
        if self.closed:
            return
        self.closed = True
        for sensor in reversed(self.sensors):
            sensor.stop()
            sensor.destroy()


def _corners(actor):
    points = []
    for vertex in actor.bounding_box.get_world_vertices(actor.get_transform()):
        point = [float(vertex.x), float(vertex.y)]
        if not any(hypot(point[0]-other[0], point[1]-other[1]) < 1e-4 for other in points):
            points.append(point)
    if len(points) != 4:
        raise ValueError("Original Native vehicle footprint incomplete")
    return points


def _body(actor):
    velocity = actor.get_velocity()
    return {"id": actor.id, "speed_mps": hypot(float(velocity.x), float(velocity.y)),
            "body_corners_xy_m": _corners(actor)}


def _step(actor, target, speed, carla):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    position = (float(transform.location.x), float(transform.location.y))
    forward = transform.get_forward_vector()
    command = control(position, (float(forward.x), float(forward.y)),
                      (float(velocity.x), float(velocity.y)), target, speed)
    actor.apply_control(carla.VehicleControl(**command))


def _seal_receipt(output, plan, ego, overtaker):
    names = ["overtake_site_original.json", "overtake_bodies_original.jsonl",
             "trace.jsonl", "video_frames.jsonl"]
    names += [name + ".mkv" for name in CAMERAS]
    names += [name + "-frames.jsonl" for name in CAMERAS]
    hashes = {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in names}
    receipt = {"case_id": plan["case_id"], "source_kind": "original_native_capture",
               "source_sha256": hashes, "ego_actor_id": ego.id, "overtaker_actor_id": overtaker.id,
               "site_sha256": plan["site_sha256"], "physical_outcome_verified": False,
               "subjective_observation_verified": False, "right_pass_permission_verified": False}
    (output / "overtake_source_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def run(plan, output, host="127.0.0.1", port=2000):
    import carla  # Loaded only for an operator's later Native run.

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in
           ("overtake_site_original.json", "overtake_source_receipt.json",
            "overtake_bodies_original.jsonl", *(camera + ".mkv" for camera in CAMERAS))):
        raise ValueError("Prior Native overtaking originals must be retained")
    client = carla.Client(host, int(port))
    client.set_timeout(30.)
    world = client.get_world()
    waypoints = verify_loaded_site(world.get_map(), plan, carla.LaneType.Driving, carla.Location)
    old = world.get_settings()
    actors = []
    cameras = None
    recorder = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        for index, blueprint_name in enumerate(("vehicle.tesla.model3", "vehicle.audi.tt")):
            spawn = waypoints[index].transform
            spawn.location.z += .5
            actor = world.try_spawn_actor(world.get_blueprint_library().find(blueprint_name), spawn)
            if actor is None:
                raise ValueError("Original overtaking participant spawn failed")
            actors.append(actor)
        ego, overtaker = actors
        (output / "overtake_site_original.json").write_bytes(Path(plan["site_source"]).read_bytes())
        recorder = SourceRecorder(output, {name: spec[2] for name, spec in CAMERA_SETUP.items()})
        cameras = Cameras(world, carla, ego, recorder.on_frame)
        observed = []
        for _ in range(160):
            _step(ego, plan["ego_target_xy_m"], plan["ego_target_speed_mps"], carla)
            _step(overtaker, plan["overtaker_target_xy_m"], plan["overtaker_target_speed_mps"], carla)
            frame = world.tick()
            cameras.wait(frame)
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError("Original Native snapshot frame mismatch")
            recorder.record_body({"frame": frame, "time_s": float(snapshot.timestamp.elapsed_seconds),
                                  "road_forward_xy": plan["forward_xy"],
                                  "ego": _body(ego), "overtaker": _body(overtaker)})
            observed.append(frame)
        cameras.verify(observed)
        result = recorder.seal()
        result["receipt"] = _seal_receipt(output, plan, ego, overtaker)
        return result
    finally:
        if cameras is not None:
            cameras.close()
        if recorder is not None and not recorder.closed:
            recorder.close()
        for actor in reversed(actors):
            actor.destroy()
        world.apply_settings(old)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--site-source")
    parser.add_argument("--site-sha256")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        if args.output_dir or args.site_source or args.site_sha256 or set(CAMERA_SETUP) != set(CAMERAS):
            raise ValueError("Invalid offline Native construction check")
        return
    if not args.output_dir:
        parser.error("--output-dir required")
    source = args.site_source or os.environ.get("OVERTAKE_SITE_SOURCE")
    digest = args.site_sha256 or os.environ.get("OVERTAKE_SITE_SHA256")
    if not source or not digest:
        raise ValueError("Native overtaking capture needs source survey and SHA-256")
    plan = prepare(CASE, source, digest)
    run(plan, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
