"""Run one source-gated 45-second Native motorist and mounted-rider encounter.

This adapter records original actor and RGB sensor samples. It reports no due
care or physical completion verdict. Original site, asset and camera plans must
already be reviewed and SHA-bound before the first world mutation.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADAPTER = _module("native_adapter")
CAMERAS = _module("native_cameras")
CAPTURE = _module("native_capture")
VIDEO = _module("video_media")
ENCOUNTER = _module("cyclist_encounter")


def _xy(actor):
    location = actor.get_location()
    return float(location.x), float(location.y)


def _speed(actor):
    velocity = actor.get_velocity()
    return math.sqrt(float(velocity.x) ** 2 + float(velocity.y) ** 2 + float(velocity.z) ** 2)


def _target_control(carla, actor, waypoint, throttle, brake, steering_error_divisor):
    current = _xy(actor)
    heading = math.radians(float(actor.get_transform().rotation.yaw))
    desired = math.atan2(waypoint["y_m"] - current[1], waypoint["x_m"] - current[0])
    error = (desired - heading + math.pi) % (2 * math.pi) - math.pi
    steer = max(-0.55, min(0.55, error / steering_error_divisor))
    actor.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))


def run(world, carla, *, case_id, site_root, site_ref, camera_review_path,
        camera_review_sha256, output_dir, steering_error_divisor=1.5):
    """Own world settings, actors, cameras, collision callback and original files."""
    kind, response = CAPTURE._target(case_id)
    source_root = Path(site_root).resolve()
    site = ADAPTER.NATIVE_SITE.verify_live(world, carla, source_root, site_ref,
                                            expected_kind=kind)
    review = CAMERAS.load_review(camera_review_path, camera_review_sha256,
                                 case_id=case_id, map_sha256=site["map_sha256"])
    root = Path(output_dir)
    if root.exists() and any(root.iterdir()):
        raise ValueError("new empty Native attempt required")
    contacts = set()
    collision_sensor = None
    with ADAPTER.OwnedEncounter(world, carla, source_root, site_ref, kind) as encounter:
        try:
            bp = world.get_blueprint_library().find("sensor.other.collision")
            if bp is None or bp.id != "sensor.other.collision":
                raise ValueError("original collision sensor unavailable")
            collision_sensor = world.spawn_actor(bp, carla.Transform(),
                                                 attach_to=encounter.actors["ego"])
            if collision_sensor is None:
                raise ValueError("original collision sensor spawn failed")
            collision_sensor.listen(lambda event: contacts.add(int(event.frame)))
            with CAMERAS.OriginalCameras(world, carla, encounter.actors["ego"], review) as cameras:
                index = -1
                first_frame = None
                ego = encounter.actors["ego"]
                rider = encounter.actors["rider"]
                person = encounter.actors["person"]
                conflict = site["ego_route"][1]

                def tick():
                    nonlocal index, first_frame
                    index += 1
                    rider_position = _xy(rider)
                    rider_distance = math.dist(rider_position,
                                               (conflict["x_m"], conflict["y_m"]))
                    ego_position = _xy(ego)
                    ego_distance = math.dist(ego_position,
                                             (conflict["x_m"], conflict["y_m"]))
                    command = ENCOUNTER.control_step(
                        _speed(ego), ego_distance,
                        rider_distance / max(_speed(rider), 0.01), response)
                    _target_control(carla, ego, site["ego_route"][1 if index < 450 else 2],
                                    command["throttle"], command["brake"], steering_error_divisor)
                    _target_control(carla, rider, site["rider_route"][1 if index < 450 else 2],
                                    0.2, 0.0, steering_error_divisor)
                    frame = int(world.tick())
                    if first_frame is None:
                        first_frame = frame
                    return frame

                def sample(frame):
                    ego_position = _xy(ego)
                    rider_position = _xy(rider)
                    person_position = _xy(person)
                    conflict_position = (conflict["x_m"], conflict["y_m"])
                    ego_dist = math.dist(ego_position, conflict_position)
                    rider_dist = math.dist(rider_position, conflict_position)
                    ego_box = ego.bounding_box.extent
                    rider_box = rider.bounding_box.extent
                    envelope = math.hypot(ego_box.x, ego_box.y) + math.hypot(rider_box.x, rider_box.y)
                    return {"source": "original_native", "case_id": case_id,
                            "map_sha256": site["map_sha256"], "frame": frame,
                            "time_s": (frame - first_frame) * 0.05,
                            "ego_actor_id": ego.id, "rider_actor_id": rider.id,
                            "rider_person_actor_id": person.id,
                            "rider_kind_observed": kind,
                            "ego_position_xy_m": list(ego_position),
                            "ego_position_z_m": float(ego.get_location().z),
                            "ego_heading_deg": float(ego.get_transform().rotation.yaw),
                            "rider_position_xy_m": list(rider_position),
                            "rider_mounted_observed": math.dist(person_position, rider_position) <= 2.0,
                            "surface_gap_m": max(0.0, math.dist(ego_position, rider_position) - envelope),
                            "ego_speed_mps": _speed(ego), "rider_speed_mps": _speed(rider),
                            "ego_brake_observed": float(ego.get_control().brake),
                            "conflict_window_observed": ego_dist <= 20 and rider_dist <= 20,
                            "contact_observed": frame in contacts}

                packet = CAPTURE.capture_attempt(
                    root, case_id=case_id, site=site, tick=tick, sample=sample,
                    camera_png=cameras.camera_png, attest_original=True,
                    site_source={"root": str(source_root), "ref": site_ref,
                                 "world": world, "carla": carla})
        finally:
            if collision_sensor is not None:
                collision_sensor.stop()
                collision_sensor.destroy()
    video_ref = VIDEO.compose(root, profile=CAMERAS.PROFILE)
    return {"case_id": case_id, "encounter_packet_sha256": hashlib.sha256(
                (root / "encounter-packet.json").read_bytes()).hexdigest(),
            "video_manifest": video_ref, "frames": CAPTURE.FRAMES,
            "restoration": "source-readback-verified", "physical_review": "pending"}
