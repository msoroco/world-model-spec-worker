"""Original Native acquisition for the C111071 straight approach.

This writer retains raw observations. It deliberately leaves signal-face and
detector-causation adjudication to source review before saved finalization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import xml.etree.ElementTree as ET

from runner import ASSIGNMENT, CAMERAS, capture_row, check
from cycle_controller import FRAMES, RATE_HZ

HERE = Path(__file__).resolve().parent
ROAD = HERE / "authored-road.xodr"


def map_check(path=ROAD):
    raw = Path(path).read_bytes()
    root = ET.fromstring(raw)
    if root.find("header").get("name") != "C111071-inoperative-signal-straight-draft":
        raise ValueError("Authored map identity differs")
    roads = {r.get("id"): r for r in root.findall("road")}
    if set(roads) != {"1", "2", "3", "4", "13", "14"}:
        raise ValueError("Straight approach and cross route absent")
    links = {(c.get("incomingRoad"), c.get("connectingRoad"))
             for c in root.findall("junction/connection")}
    if not {("1", "13"), ("3", "14")}.issubset(links):
        raise ValueError("Through junction or cross traffic link absent")
    signals = {s.get("id") for s in root.findall("road/signals/signal")}
    if not {"601", "602", "603"}.issubset(signals):
        raise ValueError("Red, arrow, or cross signal proposal absent")
    objects = {o.get("id") for o in roads["1"].findall("objects/object")}
    if not {"501", "502", "504"}.issubset(objects):
        raise ValueError("Crosswalk, stop marking, or detector proposal absent")
    for road in root.findall("road"):
        length = float(road.get("length"))
        for element in road.findall("objects/object") + road.findall("signals/signal"):
            station = float(element.get("s"))
            if not 0 <= station <= length:
                raise ValueError("Authored object or signal lies outside its source road")
    cross_road = roads["3"]
    cross_head = next(s for s in cross_road.findall("signals/signal")
                      if s.get("id") == "603")
    if float(cross_head.get("s")) < float(cross_road.get("length")) - 8:
        raise ValueError("Cross-traffic head is not near its junction approach")
    approach_objects = {o.get("id"): float(o.get("s"))
                        for o in roads["1"].findall("objects/object")}
    if not (approach_objects["504"] < approach_objects["502"] <
            approach_objects["501"] < float(roads["1"].get("length"))):
        raise ValueError("Detector, stop marking and crosswalk order differs")
    detector = next(o for o in roads["1"].findall("objects/object")
                    if o.get("id") == "504")
    if (float(detector.get("t")) != -1.75 or
            float(detector.get("width")) != 1.5 or
            float(detector.get("length")) != 2 or
            not 0 < approach_objects["502"] - approach_objects["504"] <= 3):
        raise ValueError("Detector footprint does not cover the near-line approach lane")
    return {"passed": True, "map_sha256": hashlib.sha256(raw).hexdigest(),
            "native_import_verified": False, "arrow_face_verified": False}


def road_reference(path=ROAD):
    """Derive approach boundaries from the authored road, not case labels."""
    survey = map_check(path)
    root = ET.parse(path).getroot()
    road = root.find("road[@id='1']")
    geometry = road.find("planView/geometry")
    heading = float(geometry.get("hdg"))
    if abs(heading - math.pi / 2) > 1e-6 or abs(float(geometry.get("x"))) > 1e-6:
        raise ValueError("Straight approach axis differs from source geometry")
    origin_y = float(geometry.get("y"))
    stations = {item.get("id"): float(item.get("s"))
                for item in road.findall("objects/object")}
    detector = next(item for item in road.findall("objects/object")
                    if item.get("id") == "504")
    return {"approach_road_id": 1, "lane_id": -1,
            "axis": "y", "direction": 1,
            "detector_y_m": origin_y + stations["504"],
            "detector_center_x_m": -float(detector.get("t")),
            "detector_half_length_m": float(detector.get("length")) / 2,
            "detector_half_width_m": float(detector.get("width")) / 2,
            "stop_marking_y_m": origin_y + stations["502"],
            "nearest_crosswalk_y_m": origin_y + stations["501"],
            "crosswalk_half_length_m": 1.0,
            "crosswalk_half_width_m": 3.5,
            "junction_entry_y_m": origin_y + float(road.get("length")),
            "map_sha256": survey["map_sha256"]}


def body_road_relation(row, reference):
    """Measure the full-body front against source map boundaries per tick."""
    if row.get("road_id") not in (1, 13, 4) or row.get("lane_id") != -1:
        raise ValueError("Original ego route or lane differs")
    body = row.get("body_vertices_m")
    if not isinstance(body, list) or len(body) != 8:
        raise ValueError("Original ego full body absent")
    vertices = [vertex for vertex in body if isinstance(vertex, list) and len(vertex) == 3]
    if len(vertices) != 8 or not all(math.isfinite(value) for vertex in vertices for value in vertex):
        raise ValueError("Original ego body geometry invalid")
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    front_y = max(ys)
    detector_x = reference["detector_center_x_m"]
    detector_y = reference["detector_y_m"]
    footprint_overlap = (max(xs) >= detector_x - reference["detector_half_width_m"]
                         and min(xs) <= detector_x + reference["detector_half_width_m"]
                         and max(ys) >= detector_y - reference["detector_half_length_m"]
                         and min(ys) <= detector_y + reference["detector_half_length_m"])
    return {"front_y_m": front_y,
            "front_to_stop_marking_m": reference["stop_marking_y_m"] - front_y,
            "front_to_crosswalk_m": reference["nearest_crosswalk_y_m"] - front_y,
            "entered_intersection_by_body": front_y >= reference["junction_entry_y_m"],
            "detector_footprint_intersects_ego_body": footprint_overlap,
            "detector_causation_verified": False,
            "source_map_sha256": reference["map_sha256"]}


def approach_control(front_to_stop_m, speed_mps, stop_established, cycles_complete):
    """Request a measured near-line halt before counting cross-signal cycles."""
    if not all(math.isfinite(value) for value in (front_to_stop_m, speed_mps)) or speed_mps < 0:
        raise ValueError("Original approach motion readback invalid")
    if cycles_complete:
        if not stop_established:
            raise ValueError("Cannot enter before an observed near-line stop")
        return {"throttle": .35, "brake": 0.0}
    if stop_established:
        return {"throttle": 0.0, "brake": 1.0}
    braking_distance = speed_mps * speed_mps / 8 + 1.0
    if front_to_stop_m <= braking_distance:
        return {"throttle": 0.0, "brake": 1.0}
    return {"throttle": .20 if front_to_stop_m > 5 else .08,
            "brake": 0.0}


def near_line_stop_observed(relation, speed_mps):
    distance = relation["front_to_stop_marking_m"]
    if not all(math.isfinite(value) for value in (distance, speed_mps)):
        raise ValueError("Original near-line stop readback invalid")
    return 0 <= distance <= 1.5 and speed_mps <= .05


def conflict_occupancy_from_original_bodies(participants, reference):
    """Conservatively hold for original bodies in crosswalk/junction areas."""
    pedestrian_ids, vehicle_ids = [], []
    cross_y = reference["nearest_crosswalk_y_m"]
    for row in participants:
        vertices = row.get("body_vertices_m")
        if not isinstance(vertices, list) or len(vertices) != 8 or any(
                not isinstance(vertex, list) or len(vertex) != 3 or
                not all(math.isfinite(value) for value in vertex) for vertex in vertices):
            raise ValueError("Original conflict participant body absent")
        xs = [vertex[0] for vertex in vertices]
        ys = [vertex[1] for vertex in vertices]
        kind = row.get("type_id", "")
        if kind.startswith("walker.pedestrian."):
            if (max(xs) >= -reference["crosswalk_half_width_m"] and
                    min(xs) <= reference["crosswalk_half_width_m"] and
                    max(ys) >= cross_y - reference["crosswalk_half_length_m"] and
                    min(ys) <= cross_y + reference["crosswalk_half_length_m"]):
                pedestrian_ids.append(row["actor_id"])
        elif kind.startswith("vehicle."):
            if max(xs) >= -7 and min(xs) <= 7 and max(ys) >= -7 and min(ys) <= 7:
                vehicle_ids.append(row["actor_id"])
    return {"pedestrian_body_in_adjacent_crosswalk": bool(pedestrian_ids),
            "vehicle_body_in_junction": bool(vehicle_ids),
            "pedestrian_actor_ids": sorted(pedestrian_ids),
            "vehicle_actor_ids": sorted(vehicle_ids),
            "lawful_status_review_required": True}


def camera_frame(image, native_frame, width, height):
    """Require an exact original-frame BGRA camera sample before encoding."""
    if image.frame != native_frame or image.width != width or image.height != height:
        raise ValueError("Original camera/frame/resolution join differs")
    raw = bytes(image.raw_data)
    if len(raw) != width * height * 4:
        raise ValueError("Original camera BGRA payload differs")
    return raw


def signal_heads(actors):
    """Bind distinct imported actors by exact OpenDRIVE source IDs."""
    expected = {"red": "601", "arrow": "602", "cross": "603"}
    found = {}
    for actor in actors:
        if not str(getattr(actor, "type_id", "")).startswith("traffic.traffic_light"):
            continue
        getter = getattr(actor, "get_opendrive_id", None)
        if getter is None:
            continue
        source_id = str(getter())
        for role, wanted in expected.items():
            if source_id == wanted:
                if role in found:
                    raise ValueError("Ambiguous imported Native signal: " + role)
                found[role] = actor
    if set(found) != set(expected) or len({a.id for a in found.values()}) != 3:
        raise ValueError("Three distinct imported Native signal actors required")
    return found


def signal_states(heads):
    observed = {name: str(actor.get_state()).split(".")[-1].lower()
                for name, actor in heads.items()}
    if observed["red"] != "red" or observed["arrow"] != "green" or \
            observed["cross"] not in ("green", "yellow", "red"):
        raise ValueError("Original red/arrow/cross signal readback differs")
    return observed


def nearby_device_inventory(actors):
    """Retain every imported traffic device near the junction for review."""
    devices = []
    for actor in actors:
        kind = str(getattr(actor, "type_id", ""))
        if not kind.startswith(("traffic.traffic_light", "traffic.stop", "traffic.speed_limit")):
            continue
        location = actor.get_transform().location
        if not all(math.isfinite(value) for value in (location.x, location.y, location.z)):
            raise ValueError("Imported traffic device position invalid")
        if abs(location.x) > 50 or abs(location.y) > 50:
            continue
        getter = getattr(actor, "get_opendrive_id", None)
        devices.append({"actor_id": actor.id, "type_id": kind,
                        "opendrive_id": str(getter()) if getter else None,
                        "position_m": [location.x, location.y, location.z],
                        "prohibition_review_required": True})
    return sorted(devices, key=lambda row: row["actor_id"])


def participant_rows(actors, ego_id):
    """Retain original bodies and velocities without assigning lawful status."""
    rows = []
    for actor in actors:
        kind = str(getattr(actor, "type_id", ""))
        if actor.id == ego_id or not kind.startswith(("vehicle.", "walker.pedestrian.")):
            continue
        transform = actor.get_transform()
        velocity = actor.get_velocity()
        vertices = actor.bounding_box.get_world_vertices(transform)
        if len(vertices) != 8:
            raise ValueError("Original participant body vertices absent")
        xyz = [transform.location.x, transform.location.y, transform.location.z,
               velocity.x, velocity.y, velocity.z]
        body = [[vertex.x, vertex.y, vertex.z] for vertex in vertices]
        if not all(math.isfinite(value) for value in xyz + [value for vertex in body for value in vertex]):
            raise ValueError("Original participant position or velocity invalid")
        rows.append({"actor_id": actor.id, "type_id": kind,
                     "position_m": xyz[:3], "velocity_mps": xyz[3:],
                     "body_vertices_m": body,
                     "crosswalk_occupancy_review_required": True,
                     "lawful_status_review_required": True})
    return sorted(rows, key=lambda row: row["actor_id"])


def _runtime_paths():
    for parent in HERE.parents:
        package = parent / "runtime/scenario_pipeline"
        python = parent / "runtime/python"
        if package.is_dir() and python.is_dir():
            sys.path[:0] = [str(package), str(python)]
            return
    raise RuntimeError("Current runtime module paths absent")


def validate_attempt_directory(output, config):
    """Accept only a fresh directory or the exact materialized capture bundle."""
    output = Path(output)
    if output.exists():
        if not output.is_dir() or not (output / "config.json").is_file() or any(
                (output / name).exists() for name in
                ("capture", "native_raw_readback.jsonl", "video_frames.jsonl")):
            raise ValueError("Use a fresh exact materialized Native attempt")
        if json.loads((output / "config.json").read_text()) != config:
            raise ValueError("Materialized exact case configuration differs")
        return "materialized"
    return "new"


def capture(output_dir, config_path, host="127.0.0.1", port=2000):
    """Run a fresh 600-tick attempt; fail closed on any missing source readback."""
    config = json.loads(Path(config_path).read_text())
    check(config)
    survey = map_check()
    reference = road_reference()
    output = Path(output_dir).resolve()
    attempt_kind = validate_attempt_directory(output, config)
    import carla
    _runtime_paths()
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit

    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    original = client.get_world()
    if saved["settings"].synchronous_mode or any(a.type_id.startswith(
            ("vehicle.", "walker.", "sensor.", "controller.")) for a in original.get_actors()):
        raise RuntimeError("Requires an exclusive idle asynchronous Native world")
    owned, encoders, camera_queues = [], {}, {}
    capture_writer = None
    changed = False
    success = False
    encoder_exits = {}
    try:
        world = client.generate_opendrive_world(ROAD.read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=25, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        mapping = world.get_map()
        start = mapping.get_waypoint(carla.Location(x=1.75, y=-30, z=1),
                                     project_to_road=True, lane_type=carla.LaneType.Driving)
        if start is None or start.road_id != 1 or start.lane_id != -1:
            raise RuntimeError("Native straight approach lane differs")
        heads = signal_heads(world.get_actors())
        device_inventory = nearby_device_inventory(world.get_actors())
        if not {actor.id for actor in heads.values()}.issubset(
                {row["actor_id"] for row in device_inventory}):
            raise RuntimeError("Imported governing device missing from local survey")
        heads["red"].set_state(carla.TrafficLightState.Red)
        heads["arrow"].set_state(carla.TrafficLightState.Green)
        for actor in heads.values():
            actor.freeze(True)
        heads["cross"].set_state(carla.TrafficLightState.Green)
        signal_states(heads)
        if attempt_kind == "new":
            output.mkdir(parents=True)
            (output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        (output / "map-import-survey.json").write_text(json.dumps({
            **survey, "road_reference": reference,
            "native_map_sha256": hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            "approach_road_id": start.road_id, "approach_lane_id": start.lane_id,
            "signal_actors": [{"role": role, "opendrive_id": actor.get_opendrive_id(),
                "id": actor.id, "type_id": actor.type_id,
                "xyz_m": [actor.get_transform().location.x, actor.get_transform().location.y,
                          actor.get_transform().location.z]} for role, actor in heads.items()],
            "nearby_imported_devices": device_inventory,
            "other_device_prohibition_review_required": True,
            "governing_face_review_required": True,
            "detector_causation_verified": False}, indent=2) + "\n")
        library = world.get_blueprint_library()
        motorcycles = [b for b in library.filter("vehicle.*")
                       if any(token in b.id.lower() for token in ("harley", "kawasaki", "yamaha", "vespa"))]
        if not motorcycles:
            raise RuntimeError("Native motorcycle or moped blueprint absent")
        ego_bp = motorcycles[0]
        ego_bp.set_attribute("role_name", "c111071_motorcycle_subject")
        ego = world.spawn_actor(ego_bp, carla.Transform(
            carla.Location(x=1.75, y=-30, z=1), carla.Rotation(yaw=90)))
        owned.append(ego)
        initial_vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
        if len(initial_vertices) != 8:
            raise RuntimeError("Initial original motorcycle body absent")
        initial_distance = reference["stop_marking_y_m"] - max(v.y for v in initial_vertices)
        if not 5 < initial_distance < 30:
            raise RuntimeError("Initial motorcycle approach distance differs")
        plans = (("overview", 0, -18, 22, -35),
                 ("approach", 1.75, -24, 9, -15),
                 ("reference_corner", -12, -12, 10, -25),
                 ("driver_reference", 1.75, -5, 8, -40))
        for (name, width, height), (_, x, y, z, pitch) in zip(CAMERAS, plans):
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("sensor_tick", 1 / RATE_HZ), ("fov", 85)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(sensor)
            camera_queues[name] = queue.Queue()
            sensor.listen(camera_queues[name].put)
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}",
                "-r", str(RATE_HZ), "-i", "pipe:0", "-an", "-c:v", "ffv1",
                "-level", "1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        capture_writer = PipelineCapture(client, ego, output, config["case_id"],
                                         required_observations=config.get("required_atoms", []))
        with (output / "native_raw_readback.jsonl").open("x") as samples, \
             (output / "video_frames.jsonl").open("x") as frame_map:
            t0 = None
            prior_cross = None
            observed_cycles = 0
            stopped_near_line = False
            phase_tick = 0
            prior_relation = {"front_to_stop_marking_m": initial_distance}
            prior_speed = 0.0
            prior_conflict = False
            target_cycles = 1 if config["case_variant"] == "one_cycle" else 2
            for index in range(FRAMES):
                # Start the requested cycle after the measured near-line halt.
                # Post-tick readback alone advances the completed-cycle count.
                phase = ("green", "yellow", "red")[(phase_tick % 120) // 40]
                heads["cross"].set_state({
                    "green": carla.TrafficLightState.Green,
                    "yellow": carla.TrafficLightState.Yellow,
                    "red": carla.TrafficLightState.Red}[phase])
                before_entry = prior_relation.get("front_to_crosswalk_m", 1) > 0
                hold = observed_cycles < target_cycles or (before_entry and prior_conflict)
                motion = approach_control(
                    prior_relation["front_to_stop_marking_m"],
                    prior_speed, stopped_near_line, not hold)
                ego.apply_control(carla.VehicleControl(
                    throttle=motion["throttle"], brake=motion["brake"]))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError("Native tick/snapshot frame differs")
                if t0 is None:
                    t0 = snap.timestamp.elapsed_seconds
                elapsed = snap.timestamp.elapsed_seconds - t0
                waypoint = mapping.get_waypoint(ego.get_transform().location,
                    project_to_road=True, lane_type=carla.LaneType.Driving)
                signal_state = signal_states(heads)
                cross = signal_state["cross"]
                if stopped_near_line and prior_cross == "red" and cross == "green":
                    observed_cycles += 1
                prior_cross = cross
                row = capture_row(index, native_frame, elapsed, ego, waypoint, signal_state)
                relation = body_road_relation(row, reference)
                if not stopped_near_line and near_line_stop_observed(relation, row["speed_mps"]):
                    stopped_near_line = True
                    phase_tick = 0
                    prior_cross = "green"
                elif stopped_near_line:
                    phase_tick += 1
                prior_relation = relation
                prior_speed = row["speed_mps"]
                row["road_relation_from_original_body"] = relation
                row["stop_established_from_original_body_and_speed"] = stopped_near_line
                row["signal_face_review_required"] = True
                row["detector_physical_cause_verified"] = False
                row["controller_cycle_count_from_readback"] = observed_cycles
                row["controller_target_cycles"] = target_cycles
                row["controller_hold_request"] = hold
                row["signal_actor_ids"] = {role: actor.id for role, actor in heads.items()}
                row["other_participant_original_readback"] = participant_rows(
                    world.get_actors(), ego.id)
                conflict = conflict_occupancy_from_original_bodies(
                    row["other_participant_original_readback"], reference)
                row["conservative_conflict_body_occupancy"] = conflict
                prior_conflict = (conflict["pedestrian_body_in_adjacent_crosswalk"] or
                                  conflict["vehicle_body_in_junction"])
                capture_writer.capture(native_frame, elapsed, extra={"c111071_raw": row})
                mapped = {}
                for name, width, height in CAMERAS:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = camera_queues[name].get(timeout=30)
                    encoders[name].stdin.write(camera_frame(image, native_frame, width, height))
                    mapped[name] = image.frame
                row["camera_native_frames"] = mapped
                samples.write(json.dumps(row, allow_nan=False) + "\n")
                frame_map.write(json.dumps({"video_frame": index, "native_frame": native_frame,
                    "time_s": elapsed, "camera_native_frames": mapped}) + "\n")
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            encoder_exits[name] = process.wait(timeout=180)
            if encoder_exits[name] or not (output / (name + ".mkv")).is_file():
                raise RuntimeError("Original camera encoding failed: " + name + ": " + stderr.decode()[-400:])
        capture_writer.close(confirmed=True)
        capture_writer = None
        success = True
        return {"frames": FRAMES, "source_run": str(output),
                "physical_signal_face_review_required": True,
                "detector_causation_verified": False}
    finally:
        cleanup_errors = []
        if capture_writer is not None:
            try:
                capture_writer.close(confirmed=False)
            except BaseException as exc:
                cleanup_errors.append("capture close: " + str(exc))
        for process in encoders.values():
            try:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            except BaseException as exc:
                cleanup_errors.append("encoder cleanup: " + str(exc))
        for actor in reversed(owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                cleanup_errors.append("actor cleanup: " + str(exc))
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                cleanup_errors.append("world restore: " + str(exc))
                restored = None
            if success and not cleanup_errors:
                seal_capture(output, frames=FRAMES, restoration=restored,
                             errors=[], encoder_exit_codes=encoder_exits,
                             context={"case_id": config["case_id"]})
                record_native_exit(output)
        if cleanup_errors:
            raise RuntimeError("Original Native attempt cleanup failed: " + "; ".join(cleanup_errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--config")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(map_check(), sort_keys=True))
    elif args.output_dir and args.config:
        print(json.dumps(capture(args.output_dir, args.config, args.host, args.port)))
    else:
        parser.error("--output-dir and --config required for live acquisition")
