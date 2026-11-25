"""Three exact subsection 2 Native cases; --check never imports CARLA."""

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

from officer_camera import CAMERAS, CAMERA_SIZES
from officer_camera_media import CameraMedia
from officer_capture_sequence import run as capture_sequence, write_receipt
from officer_construction import spawn_officer_performer
from officer_direction import PREFIX, SUFFIXES, native_bone_adapter, behavior_suffix
from officer_site import SITE, validate_site
from officer_source_intake import load_and_validate
from officer_traffic_sampler import native_sampler


ASSIGNMENT = PREFIX[:-2]
CASES = {PREFIX + suffix for suffix in SUFFIXES}
SWEEP_CASES = {f"{ASSIGNMENT}__c157964_sub2_judgment_{judgment}-{rank:04d}"
               for judgment in (3, 5) for rank in range(3)}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_config(config):
    site = validate_site()
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484B-257-2" or
            config.get("cell_id") != "C157964" or
            config.get("actor") != "motor_vehicle_driver" or
            config.get("selected_case_id") not in CASES | SWEEP_CASES or
            config.get("case", {}).get("case_id") != config.get("selected_case_id") or
            set(config.get("supported_case_ids", ())) != CASES):
        raise ValueError("Exact subsection 2 officer case identity required")
    if (config.get("rate_hz"), config.get("duration_s")) != (20, 30):
        raise ValueError("Exact officer capture requires 20 Hz and 30 seconds")
    controls = config.get("sweep_controls", {})
    if not isinstance(controls, dict) or set(controls) - {"ego_target_speed_mps", "other_release_frame"}:
        raise ValueError("Unknown physical sweep control")
    target_speed = controls.get("ego_target_speed_mps", 5.0)
    if (type(target_speed) not in (int, float) or not math.isfinite(target_speed)
            or not 0.0 <= target_speed <= 8.0):
        raise ValueError("Physical ego speed setpoint must be finite in the tested 0-8 m/s range")
    release = controls.get("other_release_frame", 360)
    if (type(release) not in (int, float) or not math.isfinite(release)
            or int(release) != release):
        raise ValueError("Physical other release frame must be an integer frame")
    if not 0 <= release < 600:
        raise ValueError("Physical other release frame must be within the 600-frame capture")
    if (config.get("site", {}).get("xodr_sha256") != site["site_sha256"] or
            config["site"].get("native_map_id") != "OpenDriveMap" or
            config["site"].get("ego_lane") != [site["ego_road_id"], site["ego_lane_id"]] or
            config["site"].get("other_lane") not in site["through_approaches"]):
        raise ValueError("Authored signed junction or both approach lanes differ")
    cameras = config.get("cameras")
    if (not isinstance(cameras, list) or
            [item.get("name") for item in cameras] != list(CAMERAS) or
            any((item.get("width"), item.get("height")) != CAMERA_SIZES[item["name"]]
                or item.get("fov_deg") != 90 for item in cameras)):
        raise ValueError("Four original cameras differ from the capture profile")
    if set(config.get("camera_mounts", {})) != set(CAMERAS):
        raise ValueError("Four original camera mounts required")
    for name, mount in config["camera_mounts"].items():
        if (not isinstance(mount, dict) or set(mount) != {"pose", "attach_to"} or
                mount["attach_to"] not in (None, "ego", "other", "officer")):
            raise ValueError("Invalid original camera mount: " + name)
    if (set(config.get("actor_blueprints", {})) != {"ego", "other", "officer"} or
            not all(config["actor_blueprints"].values())):
        raise ValueError("Three explicit Native actor blueprints required")
    for role in ("ego", "other", "officer"):
        pose = config.get("actor_transforms", {}).get(role)
        if (not isinstance(pose, dict) or set(pose) != {"location", "rotation"} or
                set(pose["location"]) != {"x", "y", "z"} or
                set(pose["rotation"]) != {"yaw", "pitch", "roll"}):
            raise ValueError("Explicit Native actor transform required: " + role)
    if (not isinstance(config.get("required_atoms"), list) or
            not all(isinstance(config.get("officer_pose", {}).get(key), dict)
                    and config["officer_pose"][key] for key in ("stop", "go")) or
            not isinstance(config.get("recording_description"), dict)):
        raise ValueError("Officer pose or recording contract missing")
    return config


def _transform(carla, pose):
    return carla.Transform(carla.Location(**pose["location"]),
                           carla.Rotation(**pose["rotation"]))


def _copy_source_packet(source_root, output):
    source_root = Path(source_root).resolve()
    packet_path = source_root / "source-packet.json"
    intake = load_and_validate(source_root, packet_path)
    if _sha(source_root / intake["source_paths"]["road"]) != _sha(SITE):
        raise ValueError("Reviewed source packet differs from authored officer site")
    retained = output / "source_review"
    retained.mkdir()
    packet = json.loads(packet_path.read_text())
    for binding in packet["sources"].values():
        path = Path(binding["path"])
        target = retained / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / path, target)
    shutil.copy2(packet_path, retained / "source-packet.json")
    load_and_validate(retained, retained / "source-packet.json")
    return retained, intake


def _hazard_plan(path, intake, frames):
    plan = json.loads(Path(path).read_text())
    rows = plan.get("frames")
    if (plan.get("format") != "worker-officer-approach-construction-plan" or
            plan.get("site_id") != intake["site_id"] or
            not isinstance(rows, list) or len(rows) != frames or
            any(not isinstance(row, dict) or row.get("frame_index") != i or
                type(row.get("approaching_hazard")) is not bool
                for i, row in enumerate(rows))):
        raise ValueError("Complete source-bound other approach plan required")
    return rows


def other_control(frame_index, frame_count, drive, release_frame=None):
    """Stage the other approach until ego's go phase; physical overlap is audited later."""
    if (type(frame_index) is not int or type(frame_count) is not int or
            frame_count < 3 or not 0 <= frame_index < frame_count or
            not isinstance(drive, dict) or
            set(drive) != {"throttle", "brake", "steer"}):
        raise ValueError("Complete other-vehicle construction command required")
    if release_frame is None:
        release_frame = frame_count * 3 // 5
    if (type(release_frame) not in (int, float) or
            not math.isfinite(release_frame) or
            int(release_frame) != release_frame or
            not 0 <= release_frame < frame_count):
        raise ValueError("Other-vehicle release frame outside capture")
    if frame_index < release_frame:
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0}
    return dict(drive)


def capture(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Materialize exact officer construction before Native capture")
    source_root = os.environ.get("OFFICER_SOURCE_ROOT")
    if not source_root:
        raise ValueError("OFFICER_SOURCE_ROOT with reviewed source packet required")
    retained, intake = _copy_source_packet(source_root, output)
    frames = config["rate_hz"] * config["duration_s"]
    plan = _hazard_plan(retained / intake["source_paths"]["other_route"], intake, frames)
    client = carla.Client(host, int(port))
    client.set_timeout(30)
    saved = snapshot(client)
    error = None
    summary = None
    try:
        world = client.generate_opendrive_world(SITE.read_text())
        if world.get_map().name != config["site"]["native_map_id"]:
            raise ValueError("Native officer map identity differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / config["rate_hz"]
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        blueprints = {}
        for role, blueprint_id in config["actor_blueprints"].items():
            blueprint = library.find(blueprint_id)
            blueprint.set_attribute("role_name", "c157964_sub2_" + role)
            blueprints[role] = blueprint
        camera_blueprints = {}
        for item in config["cameras"]:
            blueprint = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", item["width"]),
                               ("image_size_y", item["height"]), ("fov", item["fov_deg"])):
                blueprint.set_attribute(key, str(value))
            camera_blueprints[item["name"]] = blueprint
        transforms = {role: _transform(carla, pose)
                      for role, pose in config["actor_transforms"].items()}
        for role in ("ego", "other"):
            waypoint = world.get_map().get_waypoint(transforms[role].location)
            if waypoint is None or [waypoint.road_id, waypoint.lane_id] != config["site"][role + "_lane"]:
                raise ValueError("Native vehicle pose misses selected approach lane: " + role)
        mounts = {name: {"transform": _transform(carla, value["pose"]),
                         "attach_to": value["attach_to"]}
                  for name, value in config["camera_mounts"].items()}
        with ExitStack() as stack:
            actors = {}
            for role in ("ego", "other"):
                actor = world.try_spawn_actor(blueprints[role], transforms[role])
                if actor is None:
                    raise ValueError("Native vehicle spawn failed: " + role)
                stack.callback(actor.destroy)
                actors[role] = actor
            officer = stack.enter_context(spawn_officer_performer(
                world, blueprints["officer"], transforms["officer"],
                carla.Location(**config["junction_center_xyz_m"])))
            actors["officer"] = officer["actor"]
            adapter = native_bone_adapter(carla, config["officer_pose"]["stop"],
                                          config["officer_pose"]["go"])
            traffic = native_sampler(actors["other"], intake, lambda i: {
                "site_id": intake["site_id"], "other_actor_id": actors["other"].id,
                "approaching_hazard": plan[i]["approaching_hazard"],
                "source": "source_review/" + intake["source_paths"]["other_route"] +
                          "#frame-" + str(i)})
            with CameraMedia(world, output, camera_blueprints, mounts, actors) as media:
                graph = PipelineCapture(client, actors["ego"], output,
                                        config["selected_case_id"],
                                        required_observations=config["required_atoms"])
                try:
                    result = capture_sequence(
                        carla, world, actors["ego"], actors["officer"], adapter,
                        config["selected_case_id"], frame_count=frames,
                        source_root=retained, source_packet=retained / "source-packet.json",
                        other_actor=actors["other"], traffic_sampler=traffic,
                        camera_readback=media.readback,
                        target_speed_mps=config.get("sweep_controls", {}).get("ego_target_speed_mps", 5.0),
                        before_tick=lambda i: actors["other"].apply_control(
                            carla.VehicleControl(**other_control(
                                i, frames, config["drive"]["other"],
                                config.get("sweep_controls", {}).get("other_release_frame")))),
                        after_tick=lambda frame, time_s: graph.capture(frame, time_s))
                except BaseException:
                    graph.close(confirmed=False)
                    raise
                graph.close(confirmed=True)
                write_receipt(result, output / "capture-receipt.json")
                with FrameMap(output / "video_frames.jsonl") as frame_map:
                    for row in result["rows"]:
                        frame_map.append(row["carla_frame"],
                                         row["native_actor_source"]["time_s"],
                                         camera_frames={name: row["carla_frame"] for name in CAMERAS})
            summary = {"frames": len(result["rows"]),
                       "encoder_exit_codes": media.encoder.exit_codes}
    except BaseException as exc:
        error = exc
    try:
        restored = restore(client, saved)
    except BaseException as exc:
        (output / "native-run-status.json").write_text(json.dumps({
            "capture_sealed": False, "errors": [str(x) for x in (error, exc) if x]}) + "\n")
        raise
    if error is not None:
        (output / "native-run-status.json").write_text(json.dumps({
            "capture_sealed": False, "errors": [str(error)]}) + "\n")
        raise error
    seal_capture(output, frames=summary["frames"], restoration=restored, errors=[],
                 encoder_exit_codes=summary["encoder_exit_codes"],
                 context={"selected_case_id": config["selected_case_id"],
                          "reviewed_officer_direction_and_control": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    config = validate_config(json.loads(Path(__file__).with_name("config.json").read_text()))
    if args.check:
        print(json.dumps({"case_id": config["selected_case_id"],
                          "cpu_config_checked": True, "simulation_started": False}))
        return
    if not args.output_dir:
        raise ValueError("Native officer capture requires --output-dir")
    capture(config, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
