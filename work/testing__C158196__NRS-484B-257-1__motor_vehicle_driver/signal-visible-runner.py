"""Exact C158196 visible non-governing signal capture; CPU check never contacts CARLA."""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from signal_control import CAMERA_SIZES, CAMERAS, find_governing_signal, run_signal_capture


PREFIX = "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__"
PRIMARY = PREFIX + "signal_visible_not_governing"
SITE = Path(__file__).with_name("signal-visible-site.xodr")


def validate_authored_site(path=SITE):
    """Check a signed ego entrance and a distinct through-lane signal head."""
    root = ET.parse(path).getroot()
    if root.tag != "OpenDRIVE":
        raise ValueError("Signal site is not OpenDRIVE")
    roads = {road.get("id"): road for road in root.findall("road")}
    if set(roads) != {"158190", "158192", "158193", "158194", "158195", "158196"}:
        raise ValueError("Signed intersection roads differ")
    if any(roads[road].get("junction") != "158191" for road in ("158192", "158195")):
        raise ValueError("Signal site junction geometry differs")
    lanes = roads["158190"].findall("./lanes/laneSection/right/lane")
    if len(lanes) != 1 or lanes[0].get("id") != "-1" or lanes[0].get("type") != "driving":
        raise ValueError("Signed ego approach is not one-way")
    ego_signals = roads["158190"].findall("./signals/signal")
    through_signals = roads["158194"].findall("./signals/signal")
    if (len(ego_signals) != 1 or ego_signals[0].get("type") != "205" or
            ego_signals[0].get("dynamic") != "no" or len(through_signals) != 1):
        raise ValueError("Signed entrance or distinct through signal missing")
    sign, head = ego_signals[0], through_signals[0]
    if (head.get("type") != "1000001" or head.get("dynamic") != "yes" or
            head.get("id") == sign.get("id") or
            head.find("validity") is None or
            (head.find("validity").get("fromLane"), head.find("validity").get("toLane")) != ("-1", "-1") or
            sign.find("validity") is None or
            (sign.find("validity").get("fromLane"), sign.find("validity").get("toLane")) != ("-1", "-1")):
        raise ValueError("Through signal lane placement differs")
    controls = root.findall("./controller/control")
    refs = root.findall("./junction[@id='158191']/controller")
    if (len(controls) != 1 or controls[0].get("signalId") != head.get("id") or
            len(refs) != 1 or refs[0].get("id") != root.find("./controller").get("id")):
        raise ValueError("Through head lacks junction controller")
    return {"site_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "ego_road_id": 158190, "ego_lane_id": -1,
            "through_road_ids": [158194, 158195, 158196],
            "junction_id": 158191, "yield_sign_id": sign.get("id"),
            "head_signal_id": head.get("id")}


def validate_config(config):
    authored = validate_authored_site()
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-257-1", "C158196", "motor_vehicle_driver"):
        raise ValueError("Wrong exact C158196 assignment")
    if config.get("selected_case_id") != PRIMARY:
        raise ValueError("Wrong exact visible non-governing case")
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
    if (site.get("xodr_sha256") != authored["site_sha256"] or
            site.get("approach_lanes", {}).get("ego") != [158190, -1] or
            site.get("approach_lanes", {}).get("through") not in
            ([158194, -1], [158196, 1])):
        raise ValueError("Signal configuration differs from authored OpenDRIVE site")
    if (site.get("native_map_id") != context.get("native_map_id") or
            site.get("approach_lanes", {}).get("ego") != context.get("ego_route_lanes", [None])[0] or
            site.get("approach_lanes", {}).get("through") != context.get("through_route_lanes", [None])[0] or
            config.get("signal_selector", {}).get("affected_lane") != site.get("approach_lanes", {}).get("through") or
            context.get("native_signal_id") is not None or
            config.get("target_signal_state") != "Green"):
        raise ValueError("Selected signal construction and source context differ")
    if any(not context.get(key) for key in ("affected_lane_source", "signal_head_video_source",
                                           "signed_entrance_source", "junction_source",
                                           "intersection_polygon_xy_m")):
        raise ValueError("Selected signal lacks sourced sign, head or junction geometry")
    for role in ("ego", "through"):
        pose = config.get("actor_transforms", {}).get(role)
        if (not isinstance(pose, dict) or
                set(pose) != {"location", "rotation"} or
                set(pose["location"]) != {"x", "y", "z"} or
                set(pose["rotation"]) != {"yaw", "pitch", "roll"}):
            raise ValueError("Explicit Native actor transform required: " + role)
    if not isinstance(config.get("camera_mounts"), dict) or set(config["camera_mounts"]) != set(CAMERAS):
        raise ValueError("Four explicit camera mounts required")
    for name, mount in config["camera_mounts"].items():
        if (not isinstance(mount, dict) or set(mount) != {"pose", "attach_to"} or
                mount["attach_to"] not in (None, "ego", "through") or
                mount["pose"] is None):
            raise ValueError("Invalid exact source-camera mount: " + name)
    for role in ("ego", "through"):
        if not config.get("actor_blueprints", {}).get(role):
            raise ValueError("Missing exact Native vehicle blueprint: " + role)
        drive = config.get("drive", {}).get(role)
        if (not isinstance(drive, dict) or set(drive) != {"throttle", "brake", "steer"} or
                any(type(value) not in (int, float) for value in drive.values())):
            raise ValueError("Missing exact per-tick Native vehicle control: " + role)
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
    saved = snapshot(client)
    failure = None
    summary = None
    try:
        world = client.generate_opendrive_world(SITE.read_text())
        if world.get_map().name != config["site"]["native_map_id"]:
            raise ValueError("Generated Native map name differs from exact configuration")
        lane = config["signal_selector"]["affected_lane"]
        light = find_governing_signal(world, lane[0], lane[1])
        context = dict(config["signal_context"], native_signal_id=light.id)
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
        summary = run_signal_capture(world, client, output, config["site"],
                           blueprints, transforms, carla.TrafficLightState,
                           config["target_signal_state"], light.id, False,
                           context, camera_blueprints, mounts,
                           config["selected_case_id"], config["required_atoms"],
                           drive, config["rate_hz"]*config["duration_s"])
    except Exception as error:
        failure = error
    try:
        restored = restore(client, saved)
    except Exception as error:
        (output/"native-run-status.json").write_text(json.dumps({
            "case_id":config["selected_case_id"],"errors":[
                *([str(failure)] if failure else []),"World restoration failed: "+str(error)],
            "capture_sealed":False},allow_nan=False)+"\n")
        raise
    if failure is not None:
        (output/"native-run-status.json").write_text(json.dumps({
            "case_id":config["selected_case_id"],"errors":[str(failure)],
            "capture_sealed":False},allow_nan=False)+"\n")
        raise failure
    try:
        seal_capture(output, frames=config["rate_hz"]*config["duration_s"],
                     restoration=restored, errors=[],
                     encoder_exit_codes=summary["encoder_exit_codes"],
                     context={"selected_case_id":config["selected_case_id"],
                              "official_signal_and_sign_review_pending":True})
    except Exception as error:
        (output/"native-run-status.json").write_text(json.dumps({
            "case_id":config["selected_case_id"],"errors":["Capture seal failed: "+str(error)],
            "capture_sealed":False},allow_nan=False)+"\n")
        raise


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
