"""Source-bound C412593 Native right-turn capture entry point.

CPU input checks do not connect to CARLA. Runtime capture needs reviewed site,
route and camera packets and an exact materialized attempt under .runtime-work.
"""

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
from contextlib import ExitStack
from pathlib import Path
from queue import Queue
from xml.etree import ElementTree as ET

from distance_control import CASE_TARGET_FEET, DistanceController
from native_sources import CAMERAS, source_cameras, source_recorder, validate_plan
from right_turn_construction import spawn_right_turn_vehicle


ROOT = Path(__file__).resolve().parent
PREFIX = "testing__C412593__NRS-484B-413-2__motor_vehicle_driver__"
APPROACH_ROAD = 412593
CONNECTOR_ROAD = 412594
OUTGOING_ROAD = 412595
JUNCTION = 412596
APPROACH_M = 120.0


def _repo():
    for parent in (ROOT, *ROOT.parents):
        if (parent / "batch.json").is_file() and (parent / "runtime.py").is_file():
            return parent
    raise ValueError("Worker repository root not found above materialized runner")


def _district(case_name):
    return ("residential" if case_name.startswith("right_residential") else
            "other" if case_name.startswith("right_other") else "business")


def draft_xodr(district):
    """Authored geometry candidate; district and zone await Native review."""
    if district not in ("business", "residential", "other"):
        raise ValueError("Unsupported source district variant")
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C412593 right-turn " + district + " draft", version="1")

    def road(road_id, name, length, junction, x, y, heading, curvature=None):
        item = ET.SubElement(root, "road", id=str(road_id), name=name,
                             length=str(length), junction=str(junction), rule="RHT")
        geometry = ET.SubElement(ET.SubElement(item, "planView"), "geometry",
                                 s="0", x=str(x), y=str(y), hdg=str(heading),
                                 length=str(length))
        ET.SubElement(geometry, "line" if curvature is None else "arc",
                      **({} if curvature is None else {"curvature": str(curvature)}))
        ET.SubElement(item, "elevationProfile")
        ET.SubElement(item, "lateralProfile")
        section = ET.SubElement(ET.SubElement(item, "lanes"), "laneSection", s="0")
        ET.SubElement(section, "left")
        ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none")
        right = ET.SubElement(section, "right")
        lane = ET.SubElement(right, "lane", id="-1", type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a="3.6", b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="solid", color="white", width="0.12")
        return item

    approach = road(APPROACH_ROAD, "paved eastbound approach", APPROACH_M,
                    -1, -APPROACH_M, 0, 0)
    ET.SubElement(ET.SubElement(approach, "link"), "successor",
                  elementType="junction", elementId=str(JUNCTION))
    objects = ET.SubElement(approach, "objects")
    ET.SubElement(objects, "object", id="1", name="freight_loading_zone_sign",
                  type="sign", s="82", t="-5.8", zOffset="0", hdg="0",
                  width="0.12", length="0.12", height="2.4", orientation="+")
    ET.SubElement(objects, "object", id="2", name="freight_loading_bay",
                  type="parkingSpace", s="88", t="-5.5", zOffset="0", hdg="0",
                  width="2.5", length="18", height="0", orientation="+")
    if district != "other":
        for index, station in enumerate((15, 35, 55, 75, 95, 110), start=3):
            ET.SubElement(objects, "object", id=str(index),
                          name=("business_frontage_building" if district == "business"
                                else "residential_frontage_house"),
                          type="building", s=str(station), t="9", zOffset="0", hdg="0",
                          width="12", length="12", height="7", orientation="+")
    curve_length = 5 * math.pi / 2
    connector = road(CONNECTOR_ROAD, "clockwise right-turn connector",
                     curve_length, JUNCTION, 0, 0, 0, -0.2)
    connector_link = ET.SubElement(connector, "link")
    ET.SubElement(connector_link, "predecessor", elementType="road",
                  elementId=str(APPROACH_ROAD), contactPoint="end")
    ET.SubElement(connector_link, "successor", elementType="road",
                  elementId=str(OUTGOING_ROAD), contactPoint="start")
    outgoing = road(OUTGOING_ROAD, "paved southbound exit", 45,
                    -1, 5, -5, -math.pi / 2)
    ET.SubElement(ET.SubElement(outgoing, "link"), "predecessor",
                  elementType="junction", elementId=str(JUNCTION))
    junction = ET.SubElement(root, "junction", id=str(JUNCTION), name="right turn")
    connection = ET.SubElement(junction, "connection", id="0",
                               incomingRoad=str(APPROACH_ROAD),
                               connectingRoad=str(CONNECTOR_ROAD), contactPoint="start")
    ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="unicode") + "\n"


def materialize_draft_inputs(output, case_id, native_map_id, *,
                             requested_speed_mps=4.0, approach_start_m=0.0):
    """Write deterministic, source-hashed draft inputs under ignored attempt."""
    output = Path(output).resolve()
    if not output.is_relative_to(_repo() / ".runtime-work") or not output.is_dir():
        raise ValueError("Draft input output must be an ignored attempt")
    if not case_id.startswith(PREFIX) or case_id[len(PREFIX):] not in CASE_TARGET_FEET:
        raise ValueError("Unsupported exact draft case")
    if not native_map_id:
        raise ValueError("Native map readback required")
    if (type(requested_speed_mps) not in (int, float) or
            not 1 <= requested_speed_mps <= 12 or
            type(approach_start_m) not in (int, float) or
            not 0 <= approach_start_m <= 10):
        raise ValueError("Draft speed/spawn station outside bounded plan")
    name = case_id[len(PREFIX):]
    district = _district(name)
    files = ("map.xodr", "district-source.txt", "zone-source.txt",
             "route-plan.json", "site-packet.json", "camera-plan.json")
    if any((output / name).exists() for name in files):
        raise ValueError("Fresh draft source paths required")
    (output / "map.xodr").write_text(draft_xodr(district))
    map_sha = _sha(output / "map.xodr")
    district_text = ("Worker draft of authored OpenDRIVE frontage: " + district +
                     ". Building object uses and road frontage are planning hypotheses; "
                     "Native appearance and statutory district classification require independent review.\n")
    zone_text = ("Worker draft of authored OpenDRIVE freight-loading sign at s=82 m "
                 "and curbside bay at s=88 m on approach road 412593. Designation, "
                 "scope and Native visibility require independent review.\n")
    (output / "district-source.txt").write_text(district_text)
    (output / "zone-source.txt").write_text(zone_text)
    ref = lambda path: {"path": path, "sha256": _sha(output / path),
                        "reviewer": "worker authored draft review",
                        "review_method": "read authored OpenDRIVE objects and frozen law; physical status unverified"}
    site = {"native_map_id": native_map_id,
            "district": {"type": district,
                         "frontage_facts": "draft frontage objects at six stations" if district != "other" else "draft lacks frontage buildings",
                         "building_use_facts": "authored " + district + " object labels; legal class unverified",
                         "source": ref("district-source.txt")},
            "freight_loading_zone": {"designation": "freight_loading_zone",
                                     "road_id": APPROACH_ROAD,
                                     "marking_or_sign_evidence": "authored sign/bay objects; Native visibility unverified",
                                     "polygon_xy_m": [[-40, -8], [-20, -8], [-20, -4], [-40, -4]],
                                     "minimum_centerline_clearance_m": 1.5,
                                     "maximum_route_distance_m": 6,
                                     "source": ref("zone-source.txt")}}
    stations = lambda road, start, end, step: [[road, -1, min(start + index * step, end)]
                                               for index in range(math.ceil((end - start) / step) + 1)]
    route = {"case_id": case_id, "map_path": "map.xodr", "map_sha256": map_sha,
             "native_map_id": native_map_id, "requested_speed_mps": requested_speed_mps,
             "approach": stations(APPROACH_ROAD, approach_start_m, APPROACH_M, 2),
             "connector": stations(CONNECTOR_ROAD, 0, 5 * math.pi / 2, 0.5),
             "outgoing": stations(OUTGOING_ROAD, 0, 45, 2)}
    poses = ((-50, -10, 42, 0, -80), (-85, -14, 8, 0, -15),
             (11, -9, 12, 150, -30), (1, 0, 1.65, 0, -6))
    from native_sources import SIZES
    cameras = [{"name": name, "width": SIZES[name][0], "height": SIZES[name][1],
                "fov_deg": 90,
                "pose": dict(zip(("x", "y", "z", "yaw", "pitch"), pose))}
               for name, pose in zip(CAMERAS, poses)]
    camera_plan = {"rate_hz": 20, "duration_s": 45, "map_sha256": map_sha,
                   "cameras": cameras}
    for path, packet in (("route-plan.json", route), ("site-packet.json", site),
                         ("camera-plan.json", camera_plan)):
        (output / path).write_text(json.dumps(packet, indent=2) + "\n")
    check_inputs(case_id, route, site, camera_plan, source_root=output)
    return route, site, camera_plan


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _local_file(path, source_root=None):
    source_root = Path(ROOT if source_root is None else source_root).resolve()
    path = (source_root / path).resolve()
    if source_root not in path.parents or not path.is_file():
        raise ValueError("Source file must be inside exact C412593 package")
    return path


def check_inputs(case_id, route_plan, site_packet, camera_plan, source_root=None):
    if not isinstance(case_id, str) or not case_id.startswith(PREFIX):
        raise ValueError("Exact C412593 case ID required")
    name = case_id[len(PREFIX):]
    if name not in CASE_TARGET_FEET:
        raise ValueError("Unsupported exact C412593 case")
    if not isinstance(route_plan, dict) or not isinstance(site_packet, dict):
        raise ValueError("Source route and site packets required")
    if route_plan.get("case_id") != case_id:
        raise ValueError("Route packet is for another exact case")
    xodr = _local_file(route_plan.get("map_path", ""), source_root)
    if _sha(xodr) != route_plan.get("map_sha256"):
        raise ValueError("Source map hash differs")
    if site_packet.get("native_map_id") != route_plan.get("native_map_id"):
        raise ValueError("Native map identity differs")
    expected_district = ("residential" if name.startswith("right_residential") else
                         "other" if name.startswith("right_other") else "business")
    if site_packet.get("district", {}).get("type") != expected_district:
        raise ValueError("Case district differs from independently reviewed site")
    for key, minimum in (("approach", 3), ("connector", 2), ("outgoing", 2)):
        stations = route_plan.get(key)
        if not isinstance(stations, list) or len(stations) < minimum:
            raise ValueError("Incomplete Native waypoint stations: " + key)
        if any(not isinstance(row, list) or len(row) != 3 or
               type(row[0]) is not int or type(row[1]) is not int or
               type(row[2]) not in (int, float) or not math.isfinite(row[2]) or row[2] < 0
               for row in stations):
            raise ValueError("Invalid Native road/lane/station source")
        first = tuple(stations[0][:2])
        if any(tuple(row[:2]) != first for row in stations):
            raise ValueError("Native station chain changes lane: " + key)
        if any(not 0 < b[2] - a[2] <= 5 for a, b in zip(stations, stations[1:])):
            raise ValueError("Native station chain has a gap or reversal: " + key)
    if route_plan["approach"][-1][2] - route_plan["approach"][0][2] < 100:
        raise ValueError("Source approach lacks 100 m initial-Off buffer")
    if len({route_plan[key][0][0] for key in ("approach", "connector", "outgoing")}) != 3:
        raise ValueError("Right-turn road transitions are not distinct")
    if not isinstance(camera_plan, dict) or camera_plan.get("map_sha256") != route_plan["map_sha256"]:
        raise ValueError("Camera plan map source differs")
    validate_plan(camera_plan)
    speed = route_plan.get("requested_speed_mps")
    if type(speed) not in (int, float) or not 1 <= speed <= 12:
        raise ValueError("Bounded Native right-turn speed required")
    return {"case_id": case_id, "map_sha256": route_plan["map_sha256"],
            "duration_s": camera_plan["duration_s"], "simulation_started": False}


def _waypoints(native_map, stations):
    selected = [native_map.get_waypoint_xodr(*row) for row in stations]
    if any(wp is None or (wp.road_id, wp.lane_id) != tuple(row[:2])
           for wp, row in zip(selected, stations)):
        raise ValueError("Native lane/station source readback differs")
    return selected


def _control(actor, waypoints, target_speed):
    pose = actor.get_transform()
    xy = (pose.location.x, pose.location.y)
    points = [(wp.transform.location.x, wp.transform.location.y) for wp in waypoints]
    nearest = min(range(len(points)), key=lambda index: math.dist(xy, points[index]))
    target = points[min(nearest + 3, len(points) - 1)]
    bearing = math.degrees(math.atan2(target[1] - xy[1], target[0] - xy[0]))
    heading_error = (bearing - pose.rotation.yaw + 180) % 360 - 180
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    throttle = max(0.0, min(0.45, 0.18 * (target_speed - speed)))
    brake = max(0.0, min(1.0, 0.35 * (speed - target_speed)))
    if nearest >= len(points) - 2:
        throttle, brake = 0.0, 1.0
    return throttle, brake, max(-0.75, min(0.75, heading_error / 35))


def make_case_bundle(case_id, template, candidate_id="primary"):
    """Derive an exact-case construction without changing shared capture policy."""
    if not isinstance(case_id, str) or not case_id.startswith(PREFIX):
        raise ValueError("Exact C412593 case ID required")
    name = case_id[len(PREFIX):]
    if name not in CASE_TARGET_FEET:
        raise ValueError("Unsupported exact C412593 case")
    if template.get("entrypoint") != "runner.py" or template.get("cell_id") != "C412593":
        raise ValueError("C412593 construction template required")
    bundle = json.loads(json.dumps(template))
    configs = [row for row in bundle.get("files", []) if row.get("path") == "config.json"]
    if len(configs) != 1:
        raise ValueError("Exactly one source config required")
    config = json.loads(configs[0]["content"])
    config["selected_case_id"] = case_id
    config["supported_case_ids"] = [PREFIX + item for item in CASE_TARGET_FEET]
    config["case"] = {"case_id": case_id, "district_type": _district(name),
                      "signal_target_ft": CASE_TARGET_FEET[name],
                      "physical_acceptance_claimed": False}
    if candidate_id == "fallback1":
        config["requested_speed_mps"] = 3.0
    elif candidate_id == "fallback2":
        config["blueprint_selection_index"] = 1
    elif candidate_id == "fallback3":
        config["approach_start_m"] = 5.0
    elif candidate_id != "primary":
        raise ValueError("Unsupported C412593 fallback")
    bundle["case_id"] = case_id
    bundle["measurement_plan"]["quantities"] = [
        "continuous right-indicator path length before original course change",
        ("300-foot other-area boundary" if _district(name) == "other"
         else "100-foot business/residential boundary")]
    configs[0]["content"] = json.dumps(config, indent=2) + "\n"
    return bundle


def check_construction(folder=None):
    """Offline runtime entry point: validate materialized exact inputs only."""
    folder = Path(ROOT if folder is None else folder)
    if not (folder / "construction.json").is_file() or not (folder / "config.json").is_file():
        raise ValueError("Materialized exact construction/config required")
    config = json.loads((folder / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(PREFIX) or
            case_id[len(PREFIX):] not in CASE_TARGET_FEET or
            config.get("cell_id") != "C412593" or
            config.get("law_id") != "NRS-484B-413-2" or
            config.get("actor") != "motor_vehicle_driver" or
            config.get("rate_hz") != 20 or config.get("duration_s") != 45 or
            config.get("required_atoms") != ["sig.turn_indicator"]):
        raise ValueError("Materialized exact C412593 runtime identity differs")
    name = case_id[len(PREFIX):]
    if (case_id not in config.get("supported_case_ids", []) or
            config.get("case", {}).get("case_id") != case_id or
            config["case"].get("district_type") != _district(name) or
            config["case"].get("signal_target_ft") != CASE_TARGET_FEET[name]):
        raise ValueError("Materialized exact case district/target binding differs")
    if (type(config.get("requested_speed_mps")) not in (int, float) or
            not 1 <= config["requested_speed_mps"] <= 12 or
            type(config.get("approach_start_m", 0)) not in (int, float) or
            not 0 <= config.get("approach_start_m", 0) <= 10 or
            type(config.get("blueprint_selection_index", 0)) is not int or
            not 0 <= config.get("blueprint_selection_index", 0) <= 1):
        raise ValueError("Materialized fallback engineering knob invalid")
    if config.get("physical_completion") != {
            "criterion": "road_transition", "motion_source": "drive_history.jsonl",
            "body_key": "body_vertices_m", "road_key": "ego_road_id",
            "destination_road": OUTGOING_ROAD, "minimum_progress_m": 0.25}:
        raise ValueError("Exact source-bound right-turn physical criterion required")
    cameras = config.get("cameras")
    from native_sources import SIZES
    if not isinstance(cameras, list) or tuple(row.get("name") for row in cameras) != CAMERAS:
        raise ValueError("Materialized four original cameras required")
    if any((row.get("width"), row.get("height")) != SIZES[row["name"]]
           for row in cameras):
        raise ValueError("Materialized original camera dimensions differ")
    district = _district(case_id[len(PREFIX):])
    xml = ET.fromstring(draft_xodr(district))
    roads = {int(road.get("id")) for road in xml.findall("road")}
    objects = {item.get("name") for item in xml.findall("./road/objects/object")}
    if (roads != {APPROACH_ROAD, CONNECTOR_ROAD, OUTGOING_ROAD} or
            not {"freight_loading_zone_sign", "freight_loading_bay"} <= objects):
        raise ValueError("Authored exact right-turn map lacks road or freight zone")
    return {"case_id": case_id, "district_variant": district,
            "map_sha256": hashlib.sha256(draft_xodr(district).encode()).hexdigest(),
            "cpu_check_passed": True, "simulation_started": False}


def capture(args):
    output = Path(args.output_dir).resolve()
    repo = _repo()
    runtime_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if (not runtime_root or
            not Path(runtime_root).resolve().is_relative_to(repo / ".runtime-work") or
            not output.is_relative_to(Path(runtime_root).resolve()) or
            not (output / "construction.json").is_file() or
            not (output / "config.json").is_file()):
        raise ValueError("Use runtime.py to materialize an ignored exact attempt")
    config = json.loads((output / "config.json").read_text())
    check_construction(output)
    if args.case_id is None:
        args.case_id = config.get("selected_case_id")
    if (config.get("selected_case_id") != args.case_id or
            config.get("cell_id") != "C412593" or
            config.get("law_id") != "NRS-484B-413-2" or
            not config.get("required_atoms")):
        raise ValueError("Materialized exact C412593 config differs")
    supplied = (args.route_plan, args.site_packet, args.camera_plan)
    if any(supplied) and not all(supplied):
        raise ValueError("Complete route/site/camera source set required")
    draft_mode = not any(supplied)
    if draft_mode:
        map_text = draft_xodr(_district(args.case_id[len(PREFIX):]))
        source_root = output
    else:
        source_root = ROOT
        route_path, site_path, camera_path = map(_local_file, supplied)
        route_plan = json.loads(route_path.read_text())
        site_packet = json.loads(site_path.read_text())
        camera_plan = json.loads(camera_path.read_text())
        check_inputs(args.case_id, route_plan, site_packet, camera_plan)
        map_text = _local_file(route_plan["map_path"], source_root).read_text()

    # Imports of runtime modules occur only after the output-root guard above.
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import restore, snapshot

    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot(client)
    frames = 0
    helper = None
    completed = False
    try:
        world = client.generate_opendrive_world(map_text)
        if draft_mode:
            route_plan, site_packet, camera_plan = materialize_draft_inputs(
                output, args.case_id, world.get_map().name,
                requested_speed_mps=config["requested_speed_mps"],
                approach_start_m=config.get("approach_start_m", 0))
            route_path, site_path, camera_path = (output / name for name in
                ("route-plan.json", "site-packet.json", "camera-plan.json"))
        if (config.get("rate_hz") != camera_plan["rate_hz"] or
                config.get("duration_s") != camera_plan["duration_s"] or
                config.get("cameras") != camera_plan["cameras"] or
                config.get("requested_speed_mps") != route_plan["requested_speed_mps"]):
            raise ValueError("Materialized exact four-camera capture profile differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / camera_plan["rate_hz"]
        world.apply_settings(settings)
        native_map = world.get_map()
        if native_map.name != route_plan["native_map_id"]:
            raise ValueError("Native loaded map identity differs")
        approach = _waypoints(native_map, route_plan["approach"])
        connector = _waypoints(native_map, route_plan["connector"])
        outgoing = _waypoints(native_map, route_plan["outgoing"])
        blueprints = world.get_blueprint_library().filter("vehicle.*")
        blueprint_index = config.get("blueprint_selection_index", 0)
        if len(blueprints) <= blueprint_index:
            raise ValueError("Requested alternate Native vehicle blueprint unavailable")
        with spawn_right_turn_vehicle(world, blueprints[blueprint_index], approach, outgoing,
                                      site_packet=site_packet, site_source_root=source_root) as built:
            actor = built["actor"]
            route = built["route"]
            policy = DistanceController(args.case_id[len(PREFIX):], route["approach_points_xy_m"])
            turn_waypoints = approach + connector + outgoing
            onset = None
            initial_heading = actor.get_transform().rotation.yaw
            reached_outgoing = False
            with source_cameras(world, actor, carla, camera_plan) as sensors:
                queues = {name: Queue() for name in CAMERAS}
                for name, sensor in sensors.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as stack:
                    record = stack.enter_context(source_recorder(output))
                    helper = PipelineCapture(client, actor, output, args.case_id,
                                             required_observations=config["required_atoms"])
                    try:
                        for _ in range(camera_plan["duration_s"] * camera_plan["rate_hz"]):
                            waypoint = native_map.get_waypoint(actor.get_location(), project_to_road=False)
                            if waypoint is None:
                                raise ValueError("Native ego departed right-turn road")
                            if waypoint.road_id == route["approach_road_id"]:
                                policy.step(actor, carla.VehicleLightState)
                            throttle, brake, steer = _control(actor, turn_waypoints,
                                                                route_plan["requested_speed_mps"])
                            actor.apply_control(carla.VehicleControl(throttle=throttle,
                                                                     brake=brake, steer=steer))
                            world.tick()
                            snap = world.get_snapshot()
                            waypoint = native_map.get_waypoint(actor.get_location(), project_to_road=False)
                            if waypoint is None:
                                raise ValueError("Native ego departed source right-turn route")
                            heading = actor.get_transform().rotation.yaw
                            signed_turn = (heading - initial_heading + 180) % 360 - 180
                            if onset is None and signed_turn <= -5:
                                onset = snap.frame
                            if (waypoint.road_id, waypoint.lane_id) == (
                                    route["outgoing_road_id"], route["outgoing_lane_id"]):
                                reached_outgoing = True
                            record(snap, actor, carla, queues, waypoint)
                            helper.capture(snap.frame, snap.timestamp.elapsed_seconds)
                            frames += 1
                    finally:
                        helper.close(confirmed=frames == camera_plan["duration_s"] * camera_plan["rate_hz"])
                        helper = None
            if onset is None or not reached_outgoing:
                raise ValueError("Native source right turn not completed")
            if draft_mode:
                saved_site, saved_route = site_path, route_path
            else:
                saved_site, saved_route = output / "site_packet.json", output / "route_plan.json"
                shutil.copyfile(site_path, saved_site)
                shutil.copyfile(route_path, saved_route)
            context = {"native_map_id": native_map.name,
                       "approach_road_id": route["approach_road_id"],
                       "approach_lane_id": route["approach_lane_id"],
                       "outgoing_road_id": route["outgoing_road_id"],
                       "outgoing_lane_id": route["outgoing_lane_id"],
                       "native_route_source": _sha(saved_route),
                       "district_source": _sha(saved_site),
                       "district_type": built["site_context"]["district_type"],
                       "turn_onset_frame": onset,
                       "physical_acceptance_claimed": False}
            (output / "route_context.json").write_text(json.dumps(context, indent=2) + "\n")
            completed = True
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        restoration = restore(client, saved)
        if completed:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: 0 for name in CAMERAS},
                         context={"site_packet_bound": True,
                                  "physical_acceptance_claimed": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--route-plan")
    parser.add_argument("--site-packet")
    parser.add_argument("--camera-plan")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check_construction()))
    elif args.output_dir:
        capture(args)
    else:
        parser.error("--check or --output-dir is required")


if __name__ == "__main__":
    main()
