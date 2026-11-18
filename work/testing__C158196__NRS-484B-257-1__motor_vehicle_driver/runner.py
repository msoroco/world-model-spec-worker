"""Exact C158196 active-signal capture; CPU check never contacts CARLA."""

import argparse
import json
from pathlib import Path

from signal_control import CAMERA_SIZES, CAMERAS, run_signal_capture


PREFIX = "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__"
PRIMARY = PREFIX + "signal_controls_ego"


def validate_config(config):
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-257-1", "C158196", "motor_vehicle_driver"):
        raise ValueError("Wrong exact C158196 assignment")
    if config.get("selected_case_id") != PRIMARY:
        raise ValueError("Wrong primary exact signal case")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("Exact source capture needs 20 Hz for 30 seconds")
    if not isinstance(config.get("required_atoms"), list) or not isinstance(config.get("source_packets"), list):
        raise ValueError("Missing Core observation contract")
    cameras = config.get("cameras")
    if (not isinstance(cameras, list) or
            [item.get("name") for item in cameras] != list(CAMERAS) or
            any((item.get("width"), item.get("height")) != CAMERA_SIZES[item["name"]]
                or item.get("fov_deg") != 90 for item in cameras)):
        raise ValueError("Four original camera profile differs")
    site, context = config.get("site"), config.get("signal_context")
    if not isinstance(site, dict) or not isinstance(context, dict):
        raise ValueError("Missing authored signed intersection and signal context")
    if (site.get("native_map_id") != context.get("native_map_id") or
            site.get("approach_lanes", {}).get("ego") != context.get("ego_route_lanes", [None])[0] or
            site.get("approach_lanes", {}).get("through") != context.get("through_route_lanes", [None])[0] or
            config.get("signal_id") != context.get("native_signal_id") or
            config.get("target_signal_state") not in ("Green", "Red")):
        raise ValueError("Selected signal construction and source context differ")
    for role in ("ego", "through"):
        pose = config.get("actor_transforms", {}).get(role)
        if (not isinstance(pose, dict) or
                set(pose) != {"location", "rotation"} or
                set(pose["location"]) != {"x", "y", "z"} or
                set(pose["rotation"]) != {"yaw", "pitch", "roll"}):
            raise ValueError("Explicit Native actor transform required: " + role)
    if not isinstance(config.get("camera_mounts"), dict) or set(config["camera_mounts"]) != set(CAMERAS):
        raise ValueError("Four explicit camera mounts required")
    return config


def _transform(carla, pose):
    return carla.Transform(carla.Location(**pose["location"]),
                           carla.Rotation(**pose["rotation"]))


def capture(config, output_dir, host, port):
    import carla
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output/"construction.json").is_file():
        raise ValueError("Materialize exact construction before Native capture")
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    if world.get_map().name != config["site"]["native_map_id"]:
        raise ValueError("Dedicated Native world differs from authored signal site")
    saved = snapshot(client)
    succeeded = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/config["rate_hz"]
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        blueprints = {}
        for role in ("ego", "through"):
            blueprint = library.find(config["actor_blueprints"][role])
            blueprint.set_attribute("role_name", "c158196_257_1_" + role)
            blueprints[role] = blueprint
        camera_blueprints = {}
        for item in config["cameras"]:
            camera = library.find("sensor.camera.rgb")
            camera.set_attribute("image_size_x", str(item["width"]))
            camera.set_attribute("image_size_y", str(item["height"]))
            camera.set_attribute("fov", str(item["fov_deg"]))
            camera_blueprints[item["name"]] = camera
        mounts = {name:{"transform":_transform(carla, value["pose"]),
                        "attach_to":value["attach_to"]}
                  for name,value in config["camera_mounts"].items()}
        transforms = {role:_transform(carla, pose)
                      for role,pose in config["actor_transforms"].items()}
        def drive(index, actors):
            for role, actor in actors.items():
                plan = config["drive"][role]
                actor.apply_control(carla.VehicleControl(
                    throttle=plan["throttle"], brake=plan["brake"],
                    steer=plan["steer"]))
        run_signal_capture(world, client, output, config["site"],
                           blueprints, transforms, carla.TrafficLightState,
                           config["target_signal_state"], config["signal_id"], True,
                           config["signal_context"], camera_blueprints, mounts,
                           config["selected_case_id"], config["required_atoms"],
                           drive, config["rate_hz"]*config["duration_s"])
        succeeded = True
    finally:
        restored = restore(client, saved)
    if succeeded:
        seal_capture(output, frames=config["rate_hz"]*config["duration_s"],
                     restoration=restored, errors=[],
                     encoder_exit_codes={name:0 for name in CAMERAS},
                     context={"selected_case_id":config["selected_case_id"],
                              "official_signal_and_sign_review_pending":True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    config = validate_config(json.loads(Path("config.json").read_text()))
    if args.check:
        print(json.dumps({"case_id":config["selected_case_id"],
                          "cpu_config_checked":True,"simulation_started":False}))
        return
    if not args.output_dir:
        raise ValueError("Native capture requires --output-dir")
    capture(config, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
