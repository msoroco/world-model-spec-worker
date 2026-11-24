"""Exact four-case C157964 Native capture; --check never contacts CARLA."""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path

from officer_camera import CAMERAS, CAMERA_SIZES
from officer_construction import spawn_officer_performer
from officer_direction import PREFIX, SUFFIXES, native_bone_adapter
from officer_native_capture import NativeOfficerCapture
from officer_site import SITE, validate_site


ASSIGNMENT = PREFIX[:-2]
CASES = {PREFIX + suffix for suffix in SUFFIXES}


def validate_config(config):
    site = validate_site()
    if (config.get("assignment_id") != ASSIGNMENT or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("NRS-484B-257-1", "C157964", "motor_vehicle_driver") or
            config.get("selected_case_id") not in CASES):
        raise ValueError("Exact C157964 officer case identity required")
    if (config.get("rate_hz"), config.get("duration_s")) != (20, 30):
        raise ValueError("Officer original capture requires 20 Hz and 30 seconds")
    if config.get("site", {}).get("xodr_sha256") != site["site_sha256"]:
        raise ValueError("Officer config differs from authored junction")
    if config.get("site", {}).get("native_map_id") != "OpenDriveMap":
        raise ValueError("Native OpenDRIVE map identity required")
    if (config["site"].get("ego_lane") != [site["ego_road_id"], site["ego_lane_id"]] or
            config["site"].get("through_lane") not in site["through_approaches"]):
        raise ValueError("Officer configuration misses authored ego or through approach")
    cameras = config.get("cameras")
    if (not isinstance(cameras, list) or [item.get("name") for item in cameras] != list(CAMERAS) or
            any((item.get("width"), item.get("height")) != CAMERA_SIZES[item["name"]] or
                item.get("fov_deg") != 90 for item in cameras)):
        raise ValueError("Four original officer cameras differ from capture profile")
    if (not isinstance(config.get("required_atoms"), list) or
            set(config.get("camera_mounts", {})) != set(CAMERAS) or
            any(not isinstance(mount, dict) or set(mount) != {"pose", "attach_to"} or
                mount["attach_to"] not in (None, "ego", "through", "officer")
                for mount in config["camera_mounts"].values())):
        raise ValueError("Officer camera mounts or Core observation contract missing")
    for role in ("ego", "through", "officer"):
        pose = config.get("actor_transforms", {}).get(role)
        if (not isinstance(pose, dict) or set(pose) != {"location", "rotation"} or
                set(pose["location"]) != {"x", "y", "z"} or
                set(pose["rotation"]) != {"yaw", "pitch", "roll"}):
            raise ValueError("Explicit officer-case Native actor transform required: " + role)
    if (set(config.get("actor_blueprints", {})) != {"ego", "through", "officer"} or
            not all(config["actor_blueprints"].values()) or
            not isinstance(config.get("officer_pose", {}).get("stop"), dict) or
            not isinstance(config["officer_pose"].get("go"), dict) or
            not isinstance(config.get("officer_context"), dict) or
            config["officer_context"].get("junction_source") != "officer-site.xodr#157961" or
            config["officer_context"].get("intersection_id") != 157961 or
            config["officer_context"].get("native_map_id") != "OpenDriveMap"):
        raise ValueError("Exact officer performer, poses or sourced junction context missing")
    for role in ("ego", "through"):
        control = config.get("drive", {}).get(role)
        if (not isinstance(control, dict) or set(control) != {"throttle", "brake", "steer"} or
                any(type(value) not in (int, float) for value in control.values())):
            raise ValueError("Explicit per-tick Native vehicle control required: " + role)
    return config


def _transform(carla, pose):
    return carla.Transform(carla.Location(**pose["location"]),
                           carla.Rotation(**pose["rotation"]))


def capture(config, output_dir, host, port):
    import carla
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Materialize exact officer construction before Native capture")
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved = snapshot(client)
    failure = None
    summary = None
    try:
        world = client.generate_opendrive_world(SITE.read_text())
        if world.get_map().name != config["site"]["native_map_id"]:
            raise ValueError("Generated officer map differs from configuration")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / config["rate_hz"]
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        blueprints = {}
        for role, blueprint_id in config["actor_blueprints"].items():
            blueprint = library.find(blueprint_id)
            blueprint.set_attribute("role_name", "c157964_" + role)
            blueprints[role] = blueprint
        camera_blueprints = {}
        for item in config["cameras"]:
            blueprint = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", item["width"]),
                               ("image_size_y", item["height"]), ("fov", item["fov_deg"])):
                blueprint.set_attribute(key, str(value))
            camera_blueprints[item["name"]] = blueprint
        mounts = {name: {"transform": _transform(carla, value["pose"]),
                         "attach_to": value["attach_to"]}
                  for name, value in config["camera_mounts"].items()}
        transforms = {name: _transform(carla, pose)
                      for name, pose in config["actor_transforms"].items()}
        for role in ("ego", "through"):
            waypoint = world.get_map().get_waypoint(transforms[role].location)
            expected = config["site"][role + "_lane"]
            if waypoint is None or [waypoint.road_id, waypoint.lane_id] != expected:
                raise ValueError("Native vehicle pose misses selected approach lane: " + role)
        with ExitStack() as stack:
            actors = {}
            for role in ("ego", "through"):
                actor = world.try_spawn_actor(blueprints[role], transforms[role])
                if actor is None:
                    raise ValueError("Native officer-case vehicle spawn failed: " + role)
                stack.callback(actor.destroy)
                actors[role] = actor
            case_id = config["selected_case_id"]
            if not case_id.endswith("__no_officer_yield_nearest_view"):
                officer = stack.enter_context(spawn_officer_performer(
                    world, blueprints["officer"], transforms["officer"],
                    carla.Location(**config["junction_center_xyz_m"])))
                actors["officer"] = officer["actor"]
            context = dict(config["officer_context"], case_id=case_id,
                           officer_actor_id=getattr(actors.get("officer"), "id", None),
                           through_actor_id=actors["through"].id)
            if "officer" not in actors:
                context.update(authority_source=None, uniform_video_source=None)
            adapter = native_bone_adapter(carla, config["officer_pose"]["stop"],
                                          config["officer_pose"]["go"])
            frames = config["rate_hz"] * config["duration_s"]
            with NativeOfficerCapture(world, client, output, case_id, actors, context,
                                      camera_blueprints, mounts, config["required_atoms"],
                                      adapter, frames) as session:
                for index in range(frames):
                    for role in ("ego", "through"):
                        drive = config["drive"][role]
                        actors[role].apply_control(carla.VehicleControl(**drive))
                    session.capture_tick()
            summary = {"source_frames": session.count,
                       "encoder_exit_codes": session.encoder.exit_codes}
    except Exception as error:
        failure = error
    try:
        restored = restore(client, saved)
    except Exception as error:
        (output / "native-run-status.json").write_text(json.dumps({
            "case_id": config["selected_case_id"], "capture_sealed": False,
            "errors": [*([str(failure)] if failure else []),
                       "World restoration failed: " + str(error)]}) + "\n")
        raise
    if failure is not None:
        (output / "native-run-status.json").write_text(json.dumps({
            "case_id": config["selected_case_id"], "capture_sealed": False,
            "errors": [str(failure)]}) + "\n")
        raise failure
    seal_capture(output, frames=summary["source_frames"], restoration=restored,
                 errors=[], encoder_exit_codes=summary["encoder_exit_codes"],
                 context={"selected_case_id": config["selected_case_id"],
                          "police_authority_and_camera_review_pending": True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    config = validate_config(json.loads(Path("config.json").read_text()))
    if args.check:
        print(json.dumps({"case_id": config["selected_case_id"],
                          "cpu_config_checked": True, "simulation_started": False}))
        return
    if not args.output_dir:
        raise ValueError("Native officer capture requires --output-dir")
    capture(config, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
