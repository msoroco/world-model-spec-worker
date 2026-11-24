"""C158208 Native signed-entrance runner; --check has no CARLA dependency."""

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import SIZES, source_cameras
from officer_source import (apply_direction_pose, read_direction_pose,
                            spawn_candidate, write_candidate_packet)
from yield_capture import CAMERAS, EntrySourceWriter
from yield_construction import stage_case
from yield_context import build as build_context
from yield_motion import apply_motion
from yield_site import ROAD, ROAD_OTHER_STOP, load_native_site, validate_authored_site
from yield_stage import KINDS, PREFIX, primary

ROOT = Path(__file__).resolve().parent
STATUS_BASIS = ROOT / "native-map-plan/status-basis.txt"


def validate_config(config):
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-257-2", "C158208", "motor_vehicle_driver"):
        raise ValueError("Wrong exact C158208 assignment identity")
    case_id = config.get("selected_case_id")
    stage = primary(case_id)
    if (not isinstance(config.get("case"), dict)
            or config["case"].get("case_id") != case_id
            or config["case"].get("recording_description") != config.get("recording_description")):
        raise ValueError("Exact case recording description differs")
    if config.get("supported_case_ids") != [PREFIX + kind for kind in KINDS]:
        raise ValueError("Five exact signed-entrance case IDs required")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("Signed-entrance capture requires 20 Hz for 30 seconds")
    cameras = config.get("cameras")
    if (not isinstance(cameras, list) or [item.get("name") for item in cameras] != list(CAMERAS)
            or any((item.get("width"), item.get("height")) != SIZES[item["name"]]
                   or item.get("fov_deg") != 90 for item in cameras)):
        raise ValueError("Four source-camera profiles differ")
    if not isinstance(config.get("required_atoms"), list) or not config["required_atoms"]:
        raise ValueError("Missing original observation atoms")
    review = config.get("reference_plan")
    if not isinstance(review, dict):
        raise ValueError("Missing ordered subsection-1 reference plan")
    from yield_capture import _boundary
    _boundary(review)
    validate_authored_site(ROAD_OTHER_STOP if stage.other_stop_sign else ROAD,
                           other_stop=stage.other_stop_sign)
    if not STATUS_BASIS.is_file() or not STATUS_BASIS.read_text().strip():
        raise ValueError("Missing authored road-status basis")
    return stage


def camera_transforms(carla):
    def pose(x, y, z, yaw, pitch):
        return carla.Transform(carla.Location(x=x, y=y, z=z),
                               carla.Rotation(yaw=yaw, pitch=pitch))
    return {"overview": pose(-15, 0, 48, 0, -85),
            "approach": pose(-38, 16, 9, -30, -13),
            "reference_corner": pose(19, 25, 15, -135, -24),
            "driver_reference": pose(1.0, 0, 1.6, 0, -5)}


def camera_frame(queue, expected):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Missing original camera frame " + str(expected)) from error
        if image.frame == expected:
            return image
        if image.frame > expected:
            raise ValueError("Camera skipped Native frame " + str(expected))
    raise ValueError("Original camera frame join failed")


def _write_status_review(output, stage, site):
    source = output / "site-status-source.txt"
    source.write_text(STATUS_BASIS.read_text())
    authored = validate_authored_site(ROAD_OTHER_STOP if stage.other_stop_sign else ROAD,
                                      other_stop=stage.other_stop_sign)
    review = {"authored_map_sha256": authored["road_sha256"],
              "native_map_id": site["native_map_id"],
              "native_yield_sign_id": site["native_yield_sign_id"],
              "reviewer": "worker-authored-design; physical review pending",
              "road_status_source": source.name,
              "road_status_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "non_through_highway": True,
              "police_control": stage.officer_control_source_required,
              "traffic_signal_control": False,
              "entrance_devices": {"158208": "yield",
                                   "158212": "stop" if stage.other_stop_sign else "none",
                                   "158214": "none"},
              "intersection_polygon_xy_m": [[-8, -8], [8, -8], [8, 8], [-8, 8]],
              "physical_road_status_confirmation_pending": True}
    path = output / "status-review.json"
    path.write_text(json.dumps(review, sort_keys=True, indent=2) + "\n")
    return path


def capture(args, config, stage):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import restore, snapshot

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture to materialize the exact construction")
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot(client)
    encoders = {}
    helper = None
    frames = 0
    succeeded = False
    try:
        world, site = load_native_site(client, other_stop=stage.other_stop_sign)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        officer_factory = (lambda native_world, location_factory: spawn_candidate(
            native_world, location_factory=location_factory,
            rotation_factory=carla.Rotation, transform_factory=carla.Transform))
        with stage_case(world, stage, location_factory=carla.Location,
                        officer_factory=officer_factory) as staging:
            pose_command = None
            if staging["officer"] is not None:
                pose_command = apply_direction_pose(
                    staging["officer"], transform_factory=carla.Transform,
                    rotation_factory=carla.Rotation,
                    bone_control_factory=carla.WalkerBoneControlIn)
            status_path = _write_status_review(output, stage, site)
            context = build_context(stage, site, status_path)
            reference = config["reference_plan"]
            staging["reference_origin_xy_m"] = reference["reference_boundary"]["origin_xy_m"]
            staging["ego_forward_xy"] = reference["reference_boundary"]["ego_forward_xy"]
            with source_cameras(world, staging["ego"], camera_transforms(carla)) as cameras:
                queues = {name: Queue() for name in CAMERAS}
                for name, sensor in cameras.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as stack:
                    for name, (width, height) in SIZES.items():
                        encoders[name] = stack.enter_context(
                            FFV1Writer(output / (name + ".mkv"), width, height))
                    signs = [actor for actor in world.get_actors().filter("traffic.yield*")
                             if actor.id == site["native_yield_sign_id"]]
                    if len(signs) != 1:
                        raise ValueError("Native yield actor changed during source capture")
                    writer = EntrySourceWriter(output, context, reference, staging["ego"],
                                               staging["other"], signs[0])
                    helper = PipelineCapture(client, staging["ego"], output,
                                             config["selected_case_id"],
                                             required_observations=config["required_atoms"])
                    try:
                        for tick in range(config["rate_hz"] * config["duration_s"]):
                            control = apply_motion(world, staging, tick,
                                                   control_factory=carla.VehicleControl)
                            world.tick()
                            snap = world.get_snapshot()
                            if tick == 0 and pose_command is not None:
                                pose_readback = read_direction_pose(
                                    staging["officer"], pose_command)
                                write_candidate_packet(
                                    output, staging["officer"],
                                    pose_command=pose_command,
                                    pose_readback=pose_readback)
                            camera_ids = {}
                            for name in CAMERAS:
                                image = camera_frame(queues[name], snap.frame)
                                camera_ids[name] = image.frame
                                encoders[name].write(bytes(image.raw_data))
                            helper.capture(snap.frame, snap.timestamp.elapsed_seconds,
                                           extra={"signed_entrance_control": control})
                            writer.add(world, snap.frame, snap.timestamp.elapsed_seconds,
                                       camera_ids)
                            frames += 1
                        succeeded = True
                    finally:
                        helper.close(confirmed=succeeded)
                        helper = None
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        restoration = restore(client, saved)
    if succeeded:
        seal_capture(output, frames=frames, restoration=restoration, errors=[],
                     encoder_exit_codes={name: encoders[name].exit_code for name in CAMERAS},
                     context={"selected_case_id": stage.case_id,
                              "original_site_and_officer_review_pending": True,
                              "physical_road_status_confirmation_pending": True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    stage = validate_config(config)
    if args.check:
        print(json.dumps({"case_id": stage.case_id, "cpu_config_checked": True,
                          "simulation_started": False}))
        return
    if not args.output_dir:
        raise ValueError("Native capture requires --output-dir")
    capture(args, config, stage)


if __name__ == "__main__":
    main()
