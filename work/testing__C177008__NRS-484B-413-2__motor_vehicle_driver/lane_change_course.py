"""CPU construction for the frozen C177008 change-lane maneuver.

The generated map and trajectory are engineering inputs. Native motion, lamp
pixels, district classification, and legal acceptance require separate review.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET


ROAD_ID = 177008
LANE_WIDTH_M = 3.6
ROAD_LENGTH_M = 160.0
SAMPLE_HZ = 20
SPEED_MPS = 5.0
SIGNAL_START_S_M = 82.0
RIGHT_BLINKER_MASK = 16
LATERAL_START_S_M = 115.0
LATERAL_END_S_M = 135.0


def build_opendrive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C177008 two-lane course change",
                  version="1", north="8", south="-10", east="40", west="-120",
                  vendor="scenario-worker-demo CPU construction")
    road = ET.SubElement(root, "road", name="two marked same-direction lanes",
                         length=str(ROAD_LENGTH_M), id=str(ROAD_ID), junction="-1", rule="RHT")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-120", y="0",
                             hdg="0", length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, "line")
    ET.SubElement(road, "elevationProfile")
    ET.SubElement(road, "lateralProfile")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(section, "left")
    ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none", level="false")
    right = ET.SubElement(section, "right")
    for lane_id in (-1, -2):
        lane = ET.SubElement(right, "lane", id=str(lane_id), type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="broken" if lane_id == -1 else "solid",
                      weight="standard", color="standard", width="0.12")
    return ET.tostring(root, encoding="unicode") + "\n"


def lateral_fraction(station_m):
    if station_m <= LATERAL_START_S_M:
        return 0.0
    if station_m >= LATERAL_END_S_M:
        return 1.0
    u = (station_m - LATERAL_START_S_M) / (LATERAL_END_S_M - LATERAL_START_S_M)
    return u * u * (3.0 - 2.0 * u)


def course_sample(station_m):
    """Return a rightward course-change target and right-signal request."""
    if not 0.0 <= station_m <= ROAD_LENGTH_M:
        raise ValueError("station outside authored road")
    fraction = lateral_fraction(station_m)
    if LATERAL_START_S_M < station_m < LATERAL_END_S_M:
        u = (station_m - LATERAL_START_S_M) / (LATERAL_END_S_M - LATERAL_START_S_M)
        dyds = -LANE_WIDTH_M * 6.0 * u * (1.0 - u) / (LATERAL_END_S_M - LATERAL_START_S_M)
    else:
        dyds = 0.0
    return {
        "road_id": ROAD_ID,
        "station_m": station_m,
        "x_m": station_m - 120.0,
        "y_m": -LANE_WIDTH_M * (0.5 + fraction),
        "yaw_deg": math.degrees(math.atan(dyds)),
        "requested_right_indicator": station_m >= SIGNAL_START_S_M,
        "source_lane_id": -1,
        "target_lane_id": -2,
        "target_speed_mps": SPEED_MPS,
    }


def plan():
    count = int(ROAD_LENGTH_M * SAMPLE_HZ / SPEED_MPS)
    samples = [course_sample(i * SPEED_MPS / SAMPLE_HZ) for i in range(count + 1)]
    validate_plan(samples)
    return {
        "format": "worker-native-lane-change-course-plan",
        "cell_id": "C177008", "road_id": ROAD_ID,
        "course": "change_lane", "direction": "right",
        "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
        "other_vehicle": {"road_id": ROAD_ID, "lane_id": -2, "station_m": 150.0},
        "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
        "samples": samples,
    }


def validate_plan(samples):
    if not samples or samples[0]["requested_right_indicator"]:
        raise ValueError("no observed pre-signal course")
    if any(a["station_m"] >= b["station_m"] for a, b in zip(samples, samples[1:])):
        raise ValueError("non-increasing road station")
    first_signal = next(s for s in samples if s["requested_right_indicator"])
    first_motion = next(s for s in samples if s["y_m"] < -LANE_WIDTH_M / 2 - 1e-9)
    if first_signal["station_m"] >= first_motion["station_m"]:
        raise ValueError("signal does not precede lateral course change")
    if first_motion["station_m"] - first_signal["station_m"] < 30.48:
        raise ValueError("authored business-district lead is below 100 feet")
    if abs(samples[-1]["y_m"] + 1.5 * LANE_WIDTH_M) > 1e-9:
        raise ValueError("course does not reach target lane center")
    if any(s["road_id"] != ROAD_ID for s in samples):
        raise ValueError("lane change left the authored road")


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_diagnostic(root, signal_start_m=SIGNAL_START_S_M, district_type="business"):
    """Write a source-shaped synthetic trace for software checks only."""
    if district_type not in ("business", "residential", "other"):
        raise ValueError("Unsupported district branch")
    if not 0 < signal_start_m < LATERAL_START_S_M:
        raise ValueError("Signal start must precede course onset")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "road.xodr").write_text(build_opendrive())
    document = root / "district-site-source.txt"
    document.write_text(f"Synthetic C177008 {district_type}-area assumption for CPU branch testing; no actual site or legal district review.\n")
    map_hash, document_hash = _hash(root / "road.xodr"), _hash(document)
    packet = {"district_type": district_type, "authored_map_sha256": map_hash,
              "source_document_sha256": document_hash, "independent_review": False,
              "source_scope": "synthetic_diagnostic"}
    (root / "district-site-packet.json").write_text(json.dumps(packet, indent=2) + "\n")
    context = {"cell_id": "C177008", "course": "change_lane", "road_id": ROAD_ID,
               "source_lane_id": -1, "target_lane_id": -2,
               "source_lane_lower_y_m": -LANE_WIDTH_M,
               "district_type": district_type, "district_source_sha256": document_hash,
               "authored_map_sha256": map_hash, "source_scope": "synthetic_diagnostic",
               "district_review_verified": False}
    (root / "route_context.json").write_text(json.dumps(context, indent=2) + "\n")
    paths = {name: (root / name).open("w") for name in
             ("drive_history.jsonl", "body_history.jsonl", "video_frames.jsonl")}
    native = root / "capture/native/frames.jsonl"
    native.parent.mkdir(parents=True, exist_ok=True)
    try:
        with native.open("w") as native_file:
            for i, sample in enumerate(plan()["samples"]):
                frame, time = 1000 + i, i / SAMPLE_HZ
                x, y = sample["x_m"], sample["y_m"]
                indicator = sample["station_m"] >= signal_start_m
                drive = {"frame": frame, "time_s": time, "ego_position_xy_m": [x, y],
                         "ego_heading_deg": sample["yaw_deg"], "ego_speed_mps": SPEED_MPS,
                         "native_road_id": ROAD_ID,
                         "ego_light_mask": RIGHT_BLINKER_MASK if indicator else 0,
                         "right_indicator": indicator, "requested_indicator": indicator}
                body = {"frame": frame, "time_s": time, "road_id": ROAD_ID,
                        "body_vertices_m": [[x + dx, y + dy, 0.0] for dx in (-1.0, 1.0)
                                            for dy in (-0.7, 0.7)]}
                video = {"video_frame": i, "carla_frame": frame, "time_s": time,
                         "cameras": ["overview", "approach", "reference_corner", "driver_reference"]}
                native_row = {"frame": frame, "simulation_time": time,
                              "source_scope": "synthetic_diagnostic"}
                for name, row in (("drive_history.jsonl", drive), ("body_history.jsonl", body),
                                  ("video_frames.jsonl", video)):
                    paths[name].write(json.dumps(row) + "\n")
                native_file.write(json.dumps(native_row) + "\n")
    finally:
        for handle in paths.values():
            handle.close()
    return root


def analyze_source_trace(root):
    """Measure original-shaped rows; never infer legal or physical acceptance."""
    root = Path(root)
    required = ("road.xodr", "drive_history.jsonl", "body_history.jsonl",
                "video_frames.jsonl", "capture/native/frames.jsonl", "route_context.json",
                "district-site-packet.json", "district-site-source.txt")
    hashes = {}
    for name in required:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        hashes[name] = _hash(path)
    context = json.loads((root / "route_context.json").read_text())
    packet = json.loads((root / "district-site-packet.json").read_text())
    if (context.get("course") != "change_lane" or context.get("road_id") != ROAD_ID
            or context.get("source_lane_id") != -1 or context.get("target_lane_id") != -2):
        raise ValueError("Lane-change context differs from frozen cell construction")
    if (context.get("authored_map_sha256") != hashes["road.xodr"]
            or packet.get("authored_map_sha256") != hashes["road.xodr"]
            or context.get("district_source_sha256") != hashes["district-site-source.txt"]
            or packet.get("source_document_sha256") != hashes["district-site-source.txt"]
            or packet.get("district_type") != context.get("district_type")):
        raise ValueError("District/map source binding changed")
    district = context["district_type"]
    if district not in ("business", "residential", "other"):
        raise ValueError("Missing district branch")
    map_root = ET.fromstring((root / "road.xodr").read_text())
    driving_lanes = {int(lane.attrib["id"]): lane for lane in
                     map_root.findall("./road/lanes/laneSection/right/lane")
                     if lane.attrib.get("type") == "driving"}
    if -1 not in driving_lanes or -2 not in driving_lanes:
        raise ValueError("Two same-direction driving lanes absent")
    widths = [float(driving_lanes[lane_id].find("width").attrib["a"])
              for lane_id in (-1, -2)]
    if (any(abs(width - LANE_WIDTH_M) > 1e-9 for width in widths)
            or abs(float(context.get("source_lane_lower_y_m", 0)) + widths[0]) > 1e-9):
        raise ValueError("Source lane boundary differs from authored map")
    drive, body, video, native = (_rows(root / name) for name in
                                  ("drive_history.jsonl", "body_history.jsonl",
                                   "video_frames.jsonl", "capture/native/frames.jsonl"))
    if len(drive) < 3 or len({len(drive), len(body), len(video), len(native)}) != 1:
        raise ValueError("Source frame counts differ")
    previous = None
    path_m = 0.0
    signal_start_path = None
    first_course_change = None
    first_body_exit = None
    ever_off = False
    lower_y = float(context["source_lane_lower_y_m"])
    initial_y = drive[0]["ego_position_xy_m"][1]
    for i, (row, shape, frame, native_row) in enumerate(zip(drive, body, video, native)):
        fid, time = row.get("frame"), row.get("time_s")
        if (type(fid) is not int or type(time) not in (float, int)
                or (previous and (fid <= previous[0] or time <= previous[1]))):
            raise ValueError("Nonmonotone source time/frame")
        if (shape.get("frame") != fid or shape.get("time_s") != time
                or frame.get("carla_frame") != fid or frame.get("time_s") != time
                or frame.get("video_frame") != i or native_row.get("frame") != fid
                or native_row.get("simulation_time") != time):
            raise ValueError("Original source frame join changed")
        if native_row.get("source_scope") != context.get("source_scope"):
            raise ValueError("Native frame scope differs from route context")
        if (row.get("native_road_id") != ROAD_ID or shape.get("road_id") != ROAD_ID
                or set(frame.get("cameras", [])) !=
                {"overview", "approach", "reference_corner", "driver_reference"}):
            raise ValueError("Road identity or four-camera coverage changed")
        xy = row.get("ego_position_xy_m")
        vertices = shape.get("body_vertices_m")
        if (not isinstance(xy, list) or len(xy) != 2 or not isinstance(vertices, list)
                or len(vertices) != 4 or any(len(v) < 2 for v in vertices)):
            raise ValueError("Incomplete original ego body/path")
        if previous:
            delta = math.dist(xy, previous[2])
            elapsed = time - previous[1]
            speed = row.get("ego_speed_mps")
            if type(speed) not in (int, float) or delta > max(speed, previous[3]) * elapsed + 0.1:
                raise ValueError("Path jump exceeds source speed")
            path_m += delta
        else:
            if min(v[1] for v in vertices) < lower_y:
                raise ValueError("First body is not in source lane")
        indicator = row.get("right_indicator")
        mask = row.get("ego_light_mask")
        if (type(indicator) is not bool or type(mask) is not int
                or indicator != bool(mask & RIGHT_BLINKER_MASK)):
            raise ValueError("Right indicator differs from original light mask")
        if not indicator:
            ever_off = True
            signal_start_path = None
        elif ever_off and (previous is None or not previous[4]):
            signal_start_path = path_m
        if first_course_change is None and abs(xy[1] - initial_y) > 1e-6:
            if signal_start_path is None or not indicator:
                raise ValueError("No fully observed continuous pre-change right signal")
            first_course_change = {"frame": fid, "time_s": time, "path_m": path_m,
                                   "continuous_right_signal_distance_m": path_m - signal_start_path}
        if first_body_exit is None and min(v[1] for v in vertices) < lower_y - 1e-6:
            first_body_exit = {"frame": fid, "time_s": time, "path_m": path_m}
        previous = (fid, time, xy, float(row["ego_speed_mps"]), indicator)
    if first_course_change is None or first_body_exit is None:
        raise ValueError("No observed course change and source-lane exit")
    if first_body_exit["frame"] <= first_course_change["frame"]:
        raise ValueError("Body exit does not follow course onset")
    required_m = (300 if district == "other" else 100) * 0.3048
    return {"format": "worker-lane-change-source-measurement", "sources": hashes,
            "source_scope": context.get("source_scope"), "district_type": district,
            "district_review_verified": context.get("district_review_verified") is True,
            "required_distance_m": required_m,
            "first_course_change": first_course_change, "first_body_exit": first_body_exit,
            "observed_continuous_distance_meets_boundary":
                first_course_change["continuous_right_signal_distance_m"] >= required_m,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def finalize_source_trace(source, output):
    """Derive replay channels from saved original-shaped rows, once, on CPU."""
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError("Retain prior finalization; choose a fresh output")
    report = analyze_source_trace(source)
    rows = _rows(source / "drive_history.jsonl")
    output.mkdir(parents=True)
    channel_root = output / "channels"
    channel_root.mkdir()
    extract = {
        "ego_speed": ("m/s", lambda row: row["ego_speed_mps"]),
        "ego_heading": ("deg", lambda row: row["ego_heading_deg"]),
        "ego_road_id": ("id", lambda row: row["native_road_id"]),
        "ego_turn_indicator": ("device state", lambda row: {
            "reported_mask": row["ego_light_mask"],
            "reported_device_state": "right" if row["right_indicator"] else "off"}),
        "ego_position": ("m", lambda row: row["ego_position_xy_m"]),
    }
    evidence = []
    for name, (unit, value) in extract.items():
        relative = "channels/" + name + ".jsonl"
        with (output / relative).open("x") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "original_frame": row["frame"],
                                         "value": value(row)}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": unit, "reference": relative,
                         "sha256": _hash(output / relative)})
    result = {"format": "worker-lane-change-saved-source-analysis",
              "cell_id": "C177008", "course": "change_lane",
              "measured_values": {
                  "continuous_right_signal_distance_m":
                      report["first_course_change"]["continuous_right_signal_distance_m"],
                  "statutory_boundary_m": report["required_distance_m"],
                  "first_course_change_frame": report["first_course_change"]["frame"],
                  "first_body_exit_frame": report["first_body_exit"]["frame"]},
              "observed_continuous_distance_meets_boundary":
                  report["observed_continuous_distance_meets_boundary"],
              "source_scope": report["source_scope"],
              "source_evidence_hashes": report["sources"],
              "recording_evidence": evidence,
              "physical_acceptance_claimed": False,
              "legal_acceptance_claimed": False}
    (output / "analysis.json").write_text(json.dumps(result, indent=2,
                                                       allow_nan=False) + "\n")
    return result


def native_control(position_xy, yaw_deg, speed_mps, station_m, target_speed_mps=SPEED_MPS):
    """Bounded pure-pursuit command for the authored right lane change."""
    target = course_sample(min(ROAD_LENGTH_M, station_m + 4.0))
    dx = target["x_m"] - position_xy[0]
    dy = target["y_m"] - position_xy[1]
    desired = math.degrees(math.atan2(dy, dx))
    error = (desired - yaw_deg + 180.0) % 360.0 - 180.0
    steer = max(-0.65, min(0.65, error / 45.0))
    throttle = max(0.0, min(0.55, 0.3 * (target_speed_mps - speed_mps)))
    brake = max(0.0, min(0.5, 0.2 * (speed_mps - target_speed_mps)))
    return {"steer": steer, "throttle": throttle, "brake": brake,
            "requested_right_indicator": station_m >= SIGNAL_START_S_M,
            "target_xy_m": [target["x_m"], target["y_m"]]}


def capture_native(args, config):
    """Acquire one original CARLA run only through explicit runtime capture."""
    import carla
    from contextlib import ExitStack
    from queue import Queue
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore
    from turn_signal_measurements import (_source_cameras, _ffv1, _read_camera,
                                          set_native_right_blinker)

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture to materialize exact construction")
    if _hash(output / "road.xodr") != hashlib.sha256(build_opendrive().encode()).hexdigest():
        raise ValueError("Returned lane-change map differs from controller")
    if (config.get("cell_id") != "C177008" or config.get("course") != "change_lane"
            or config.get("rate_hz") != 20 or config.get("duration_s") != 40
            or config.get("required_atoms") != ["sig.turn_indicator"]):
        raise ValueError("Exact lane-change capture configuration required")
    cameras = config.get("cameras", [])
    sizes = {"overview": (1920, 1080), "approach": (1280, 720),
             "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
    if (not isinstance(cameras, list) or [c.get("name") for c in cameras] != list(sizes)
            or any((c.get("width"), c.get("height")) != sizes[c["name"]]
                   for c in cameras)):
        raise ValueError("Four source cameras required")
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot_world(client)
    ego = None
    collector = None
    frames = 0
    error = None
    try:
        world = client.generate_opendrive_world(build_opendrive())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        native_map = world.get_map()
        origin = native_map.get_waypoint_xodr(ROAD_ID, -1, 5.0)
        target = native_map.get_waypoint_xodr(ROAD_ID, -2, 145.0)
        if origin is None or target is None or origin.road_id != target.road_id:
            raise ValueError("Native two-lane same-road chain unavailable")
        blueprints = world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("No Native vehicle blueprint")
        transform = origin.transform
        transform.location.z += 0.5
        ego = world.try_spawn_actor(blueprints[0], transform)
        if ego is None:
            raise ValueError("Native source-lane ego spawn failed")
        with _source_cameras(world, ego, carla, cameras) as sensors:
            queues = {name: Queue() for name in sizes}
            for name, sensor in sensors.items():
                sensor.listen(lambda image, name=name: queues[name].put(image))
            with ExitStack() as stack:
                writers = {name: stack.enter_context(_ffv1(output / (name + ".mkv"), size))
                           for name, size in sizes.items()}
                frame_map = stack.enter_context(FrameMap(output / "video_frames.jsonl"))
                drive = stack.enter_context((output / "drive_history.jsonl").open("x", buffering=1))
                bodies = stack.enter_context((output / "body_history.jsonl").open("x", buffering=1))
                collector = PipelineCapture(client, ego, output,
                                            config["selected_case_id"],
                                            required_observations=config["required_atoms"])
                try:
                    for _ in range(config["duration_s"] * config["rate_hz"]):
                        pose = ego.get_transform()
                        velocity = ego.get_velocity()
                        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                        waypoint = native_map.get_waypoint(pose.location, project_to_road=False)
                        if waypoint is None or waypoint.road_id != ROAD_ID:
                            raise ValueError("Native ego left the authored road")
                        command = native_control((pose.location.x, pose.location.y),
                                                 pose.rotation.yaw, speed, waypoint.s,
                                                 config.get("requested_speed_mps", SPEED_MPS))
                        set_native_right_blinker(ego, carla.VehicleLightState,
                                                 command["requested_right_indicator"])
                        ego.apply_control(carla.VehicleControl(
                            throttle=command["throttle"], brake=command["brake"],
                            steer=command["steer"]))
                        world.tick()
                        snap = world.get_snapshot()
                        for name in sizes:
                            writers[name].write(_read_camera(queues[name], snap.frame))
                        frame_map.append(snap.frame, snap.timestamp.elapsed_seconds)
                        collector.capture(snap.frame, snap.timestamp.elapsed_seconds)
                        pose = ego.get_transform()
                        velocity = ego.get_velocity()
                        waypoint = native_map.get_waypoint(pose.location, project_to_road=False)
                        if waypoint is None or waypoint.road_id != ROAD_ID:
                            raise ValueError("Native ego left the authored road")
                        lamp = int(ego.get_light_state())
                        row = {"frame": int(snap.frame),
                               "time_s": float(snap.timestamp.elapsed_seconds),
                               "ego_position_xy_m": [float(pose.location.x), float(pose.location.y)],
                               "ego_heading_deg": float(pose.rotation.yaw),
                               "ego_speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
                               "native_road_id": int(waypoint.road_id),
                               "native_lane_id": int(waypoint.lane_id),
                               "ego_light_mask": lamp,
                               "right_indicator": bool(lamp & RIGHT_BLINKER_MASK),
                               "requested_indicator": command["requested_right_indicator"]}
                        drive.write(json.dumps(row, allow_nan=False) + "\n")
                        vertices = ego.bounding_box.get_world_vertices(pose)
                        bodies.write(json.dumps({"frame": row["frame"],
                            "time_s": row["time_s"], "road_id": row["native_road_id"],
                            "lane_id": row["native_lane_id"],
                            "body_vertices_m": [[float(v.x), float(v.y), float(v.z)]
                                                for v in vertices]}, allow_nan=False) + "\n")
                        frames += 1
                finally:
                    collector.close()
                    collector = None
        (output / "route_context.json").write_text(json.dumps({
            "cell_id": "C177008", "course": "change_lane", "road_id": ROAD_ID,
            "source_lane_id": -1, "target_lane_id": -2,
            "native_map_id": native_map.name, "source_scope": "native_unverified",
            "district_type": None, "district_review_verified": False,
            "map_sha256": _hash(output / "road.xodr")}, indent=2) + "\n")
    except BaseException as exc:
        error = exc
        raise
    finally:
        if collector is not None:
            collector.close(confirmed=False)
        if ego is not None:
            ego.destroy()
        restoration = restore(client, saved)
        if error is None:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: 0 for name in sizes},
                         context={"native_lane_change_candidate": True,
                                  "district_review_verified": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-diagnostic", action="store_true")
    parser.add_argument("--analyze", type=Path)
    parser.add_argument("--finalize-source", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if args.check:
        validate_plan(plan()["samples"])
        return
    if args.output_dir:
        config = json.loads((Path(__file__).parent / "config.json").read_text())
        capture_native(args, config)
        return
    if args.output is None:
        parser.error("--output is required for diagnostic construction")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "road.xodr").write_text(build_opendrive())
    result = plan()
    (args.output / "course-plan.json").write_text(json.dumps(result, indent=2) + "\n")
    if args.write_diagnostic:
        write_diagnostic(args.output / "diagnostic")
    if args.finalize_source:
        print(json.dumps(finalize_source_trace(args.finalize_source, args.output / "saved-finalization"), indent=2))
        return
    if args.analyze:
        print(json.dumps(analyze_source_trace(args.analyze), indent=2))
        return
    print(json.dumps({"course": result["course"], "samples": len(result["samples"]),
                      "first_signal_s_m": next(s["station_m"] for s in result["samples"] if s["requested_right_indicator"]),
                      "lateral_start_s_m": LATERAL_START_S_M,
                      "lead_m": LATERAL_START_S_M - SIGNAL_START_S_M,
                      "native_execution": "pending", "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
