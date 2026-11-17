"""Candidate opposite-turn capture loop for CPU and future Native site binding.

The caller supplies a frame-aligned camera collector and source writer. This
module does not mark a candidate site reviewed or create accepted media.
"""

import math
import json
import hashlib
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue
from shapely.geometry import MultiPoint, Polygon

from camera_setup import SIZES, source_cameras
from camera_encoder import FFV1Writer
from capture_sources import _actor, _native_state, _stop_state
from opposite_turn_construction import (construct_opposite_turn_pair,
                                        command_opposite_turn_pair)


def run_candidate_opposite_turn(world, carla, site, turning_role, blueprints,
                                transforms, release_frames, target_speeds_mps,
                                frames, collect_camera_frames, write_source,
                                camera_factory=None, lookahead_m=5.0):
    """Apply paired controls and retain one original source record per tick."""
    if type(frames) is not int or not 1 <= frames <= 1100:
        raise ValueError("Bounded positive capture frame count required")
    if not callable(collect_camera_frames) or not callable(write_source):
        raise ValueError("Four-camera collector and source writer required")
    progress = {"ego": 1, "other": 1}
    frame_ids = []
    with construct_opposite_turn_pair(world, blueprints, transforms,
                                      site, turning_role) as built:
        actors = built["actors"]
        with ExitStack() as camera_stack:
            if camera_factory is not None:
                collect_camera_frames = camera_stack.enter_context(camera_factory(world, actors))
            for index in range(frames):
                command = command_opposite_turn_pair(
                carla, actors, site, progress, index, release_frames,
                target_speeds_mps, turning_role, lookahead_m=lookahead_m)
                native_frame = world.tick()
                if type(native_frame) is not int or (frame_ids and native_frame <= frame_ids[-1]):
                    raise ValueError("Increasing original Native frame IDs required")
                cameras = collect_camera_frames(native_frame)
                if not isinstance(cameras, dict) or set(cameras) != set(SIZES) or any(
                    type(frame) is not int or frame != native_frame
                    for frame in cameras.values()):
                    raise ValueError("All four camera sources must join original Native frame")
                bodies = {role: _actor(actor, world.get_map())
                          for role, actor in actors.items()}
                if bodies["ego"]["actor_id"] == bodies["other"]["actor_id"]:
                    raise ValueError("Distinct original Native actors required")
                write_source({"native_frame": native_frame,
                          "frame_index": index,
                          "turning_role": turning_role,
                          "camera_source_frames": cameras,
                          "actor_sources": bodies,
                          "applied_decisions": command["decisions"],
                          "physical_or_legal_acceptance_claimed": False})
                frame_ids.append(native_frame)
    return {"frames_recorded": len(frame_ids),
            "first_native_frame": frame_ids[0],
            "last_native_frame": frame_ids[-1],
            "physical_or_legal_acceptance_claimed": False}


def _camera_pose(carla, values):
    if (not isinstance(values, list) or len(values) != 6 or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in values)):
        raise ValueError("Finite six-value camera pose required")
    return carla.Transform(carla.Location(x=values[0], y=values[1], z=values[2]),
                           carla.Rotation(yaw=values[3], pitch=values[4], roll=values[5]))


def _joined_image(queue, frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Missing original source-camera frame") from error
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise ValueError("Source camera skipped original Native frame")
    raise ValueError("Camera frame join exhausted")


def verify_native_signal_governance(site, governed_lights):
    """Read back the two exact signal actors and their governed approach lanes."""
    signal_ids = site.get("governed_signal_ids")
    lanes = site.get("expected_approach_lanes")
    if (not isinstance(governed_lights, dict) or set(governed_lights) != {"ego", "other"} or
            not isinstance(signal_ids, dict) or set(signal_ids) != {"ego", "other"} or
            not isinstance(lanes, dict) or set(lanes) != {"ego", "other"} or
            signal_ids["ego"] == signal_ids["other"]):
        raise ValueError("Two distinct sourced governed Native signal actors required")
    for role in ("ego", "other"):
        light = governed_lights[role]
        if type(signal_ids[role]) is not int or signal_ids[role] <= 0 or light.id != signal_ids[role]:
            raise ValueError("Native signal actor ID differs from reviewed site: " + role)
        expected = lanes[role]
        if (not isinstance(expected, list) or len(expected) != 2 or
                any(type(value) is not int for value in expected)):
            raise ValueError("Sourced approach lane required: " + role)
        try:
            governed = {(int(waypoint.road_id), int(waypoint.lane_id))
                        for waypoint in light.get_affected_lane_waypoints()}
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Native signal lane readback unavailable: " + role) from error
        if tuple(expected) not in governed:
            raise ValueError("Native signal does not govern sourced approach lane: " + role)
    return {role: signal_ids[role] for role in ("ego", "other")}


def _validate_candidate_construction(root, config, site, turning_role,
                                     release_frames, target_speeds_mps, frames,
                                     transforms=None, lookahead_m=5.0):
    """Bind a preseeded exact attempt to the supplied construction inputs."""
    case = "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__opposite_left_turn"
    if (config.get("selected_case_id") != case or
            config.get("law_id") != "NRS-484B-250-2" or
            config.get("cell_id") != "C125751" or
            config.get("turning_role") != turning_role or
            config.get("site") != site):
        raise ValueError("Exact C125751 candidate case/site identity required")
    try:
        site_digest = hashlib.sha256(json.dumps(site, sort_keys=True,
                                                allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError) as error:
        raise ValueError("Serializable finite candidate site required") from error
    construction = json.loads((root / "construction.json").read_text())
    # The pinned offline/capture launcher writes the full inline proposal at
    # construction.json. Preserve the same binding for direct candidate tests.
    if construction.get("case_id") == case and "candidate_construction" in construction:
        construction = construction["candidate_construction"]
    if (construction.get("selected_case_id") != case or
            construction.get("site_sha256") != site_digest or
            construction.get("turning_role") != turning_role or
            construction.get("release_frames") != release_frames or
            construction.get("target_speeds_mps") != target_speeds_mps or
            construction.get("lookahead_m", 5.0) != lookahead_m or
            construction.get("frames") != frames):
        raise ValueError("Exact C125751 candidate construction differs from attempted controls")
    if (type(frames) is not int or not 2 <= frames <= 1100 or
            type(lookahead_m) not in (int, float) or not math.isfinite(lookahead_m) or lookahead_m <= 0 or
            not isinstance(release_frames, dict) or set(release_frames) != {"ego", "other"} or
            any(type(value) is not int or not 1 <= value < frames for value in release_frames.values()) or
            not isinstance(target_speeds_mps, dict) or set(target_speeds_mps) != {"ego", "other"} or
            any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                for value in target_speeds_mps.values())):
        raise ValueError("Bounded paired candidate control schedule required")
    variant = construction.get("candidate_variant", "primary")
    if variant != "primary" or "candidate_plan" in config:
        from opposite_turn_construction import validate_opposite_fallbacks
        plan = config.get("candidate_plan")
        if not isinstance(plan, dict) or set(plan) != {"primary", "fallbacks"}:
            raise ValueError("Complete predeclared opposite-turn candidate plan required")
        validated = validate_opposite_fallbacks(plan["primary"], plan["fallbacks"], turning_role)
        if variant not in {"primary", *validated["fallbacks"]}:
            raise ValueError("Declared opposite-turn candidate variant required")
        chosen = validated["primary"] if variant == "primary" else validated["fallbacks"][variant]
        attempted = {"site": site, "transforms": transforms,
                     "release_frames": release_frames,
                     "target_speeds_mps": target_speeds_mps, "frames": frames,
                     "lookahead_m": lookahead_m}
        if attempted != {key: chosen[key] for key in attempted}:
            raise ValueError("Opposite-turn candidate differs from predeclared variant")


def capture_candidate_media(output_dir, world, carla, site, turning_role,
                            blueprints, transforms, release_frames,
                            target_speeds_mps, frames, governed_lights=None,
                            client=None, original_capture_factory=None,
                            lookahead_m=5.0):
    """Write four FFV1 sources, frame map and paired original actor records.

    This is a candidate capture path; the exact selected manifest, source site
    review, finalizer and independent delivery audit are separate requirements.
    """
    root = Path(output_dir)
    if not root.is_dir():
        raise ValueError("Existing candidate capture directory required")
    existing = {path.name for path in root.iterdir()}
    if client is None:
        if existing:
            raise ValueError("Fresh existing candidate capture directory required")
        case_id = "candidate_opposite_turn"
    else:
        if not {"config.json", "construction.json"} <= existing:
            raise ValueError("Exact candidate config and construction required before Native capture")
        config = json.loads((root / "config.json").read_text())
        case_id = config.get("selected_case_id")
        _validate_candidate_construction(root, config, site, turning_role,
                                         release_frames, target_speeds_mps, frames,
                                         transforms, lookahead_m)
        from opposite_site_probe import verify_opposite_site_packet
        reviewed = verify_opposite_site_packet(config, root)
        if reviewed["diagnostic_only"]:
            raise ValueError("Diagnostic opposite-turn site cannot enter Native capture")
        verify_native_signal_governance(site, governed_lights)
        generated = {"capture", "road_geometry.json", "turn_route_context.json",
                     "stop_context.json", "signal_context.json", "body_history.jsonl",
                     "crossing_history.jsonl", "stop_history.jsonl", "signal_history.jsonl",
                     "video_frames.jsonl", "trace.jsonl", "spawn_attempt.json",
                     *(name + ".mkv" for name in SIZES)}
        if existing & generated:
            raise ValueError("Retain prior candidate acquisition; choose a fresh attempt")
    if original_capture_factory is not None and client is None:
        raise ValueError("Original capture factory requires the Native client")
    if client is not None:
        if original_capture_factory is None:
            from pipeline_capture import PipelineCapture
            original_capture_factory = PipelineCapture
    camera_values = site.get("cameras")
    if not isinstance(camera_values, dict) or set(camera_values) != set(SIZES):
        raise ValueError("Four reviewed camera poses required")
    polygon = Polygon(site.get("crossing_polygon_xy_m", []))
    if (not polygon.is_valid or polygon.area <= 0 or
            not site.get("crossing_polygon_source")):
        raise ValueError("Sourced Native crossing polygon required")
    junction_id = site.get("native_junction_id")
    headings = site.get("approach_headings_deg")
    if (type(junction_id) is not int or junction_id <= 0 or
            not isinstance(headings, dict) or set(headings) != {"ego", "other"} or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in headings.values()) or
            not site.get("approach_geometry_source")):
        raise ValueError("Native candidate junction and approach source required")
    if governed_lights is not None:
        signal_ids = site.get("governed_signal_ids")
        lanes = site.get("expected_approach_lanes")
        if (not isinstance(governed_lights, dict) or set(governed_lights) != {"ego", "other"} or
                not isinstance(signal_ids, dict) or set(signal_ids) != {"ego", "other"} or
                any(type(signal_ids[role]) is not int or signal_ids[role] <= 0 or
                    getattr(governed_lights[role], "id", None) != signal_ids[role]
                    for role in ("ego", "other")) or
                signal_ids["ego"] == signal_ids["other"] or
                not site.get("device_inventory_source") or
                not site.get("native_map_name") or
                not isinstance(lanes, dict) or set(lanes) != {"ego", "other"} or
                any(not isinstance(lanes[role], list) or len(lanes[role]) != 2 or
                    any(type(value) is not int for value in lanes[role])
                    for role in ("ego", "other"))):
            raise ValueError("Two sourced governed Native signal actors required")
    references = site.get("selected_stop_references")
    if not isinstance(references, dict) or set(references) != {"ego", "other"}:
        raise ValueError("Source-selected stop references required for both approaches")
    for role, reference in references.items():
        if (not isinstance(reference, dict) or
                reference.get("kind") not in ("marked_stop_line", "near_side_crosswalk", "nearest_view_point") or
                not reference.get("geometry_source") or not reference.get("reference_review_source")):
            raise ValueError("Sourced candidate stop reference required: " + role)
        segment = reference.get("segment_xy_m")
        if (not isinstance(segment, list) or len(segment) != 2 or
                any(not isinstance(point, list) or len(point) != 2 or
                    any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
                    for point in segment) or
                math.dist(segment[0], segment[1]) <= 0):
            raise ValueError("Finite nondegenerate stop reference segment required: " + role)
    poses = {name: _camera_pose(carla, camera_values[name]) for name in SIZES}
    (root / "road_geometry.json").write_text(json.dumps({
        "intersection_id": junction_id,
        "intersection_polygon_xy_m": site["crossing_polygon_xy_m"],
        "intersection_polygon_source": site["crossing_polygon_source"],
        "ego_approach_heading_deg": headings["ego"],
        "other_approach_heading_deg": headings["other"],
        "approach_geometry_source": site["approach_geometry_source"],
        "review_status": "candidate_only",
        "site_review_sha256": reviewed["packet_sha256"] if client is not None else None}, allow_nan=False) + "\n")
    (root / "turn_route_context.json").write_text(json.dumps({
        "intersection_id": junction_id, "routes": site["routes"],
        "approach_geometry_source": site["approach_geometry_source"],
        "site_review_sha256": reviewed["packet_sha256"] if client is not None else None,
        "turn_intention_source": "Native route candidate; original trajectory requires review",
        "review_status": "candidate_only"}, allow_nan=False) + "\n")
    (root / "stop_context.json").write_text(json.dumps({
        "intersection_id": junction_id,
        "selected_references": references,
        "site_review_sha256": reviewed["packet_sha256"] if client is not None else None,
        "review_status": "candidate_only"}, allow_nan=False) + "\n")
    if governed_lights is not None:
        (root / "signal_context.json").write_text(json.dumps({
            "intersection_id": junction_id,
            "native_signal_id": signal_ids["ego"],
            "other_native_signal_id": signal_ids["other"],
            "native_map_id": site["native_map_name"],
            "governed_road_id": lanes["ego"][0],
            "governed_lane_id": lanes["ego"][1],
            "other_governed_road_id": lanes["other"][0],
            "other_governed_lane_id": lanes["other"][1],
            "device_inventory_source": site["device_inventory_source"],
            "site_review_sha256": reviewed["packet_sha256"] if client is not None else None,
            "review_status": "candidate_only"}, allow_nan=False) + "\n")
    from worker_exchange.native_output import FrameMap
    with ExitStack() as stack:
        body_stream = stack.enter_context((root / "body_history.jsonl").open("x", buffering=1))
        crossing_stream = stack.enter_context((root / "crossing_history.jsonl").open("x", buffering=1))
        stop_stream = stack.enter_context((root / "stop_history.jsonl").open("x", buffering=1))
        signal_stream = (stack.enter_context((root / "signal_history.jsonl").open("x", buffering=1))
                         if governed_lights is not None else None)
        frame_map = stack.enter_context(FrameMap(root / "video_frames.jsonl"))
        frame_times = {}
        original_capture = None

        @contextmanager
        def camera_factory(active_world, actors):
            nonlocal original_capture
            if original_capture_factory is not None:
                original_capture = stack.enter_context(original_capture_factory(
                    client, actors["ego"], root, case_id))
            sensors = stack.enter_context(source_cameras(active_world, actors["ego"], poses))
            queues = {name: Queue() for name in SIZES}
            for name, sensor in sensors.items():
                sensor.listen(lambda image, camera_name=name: queues[camera_name].put(image))
            writers = {name: stack.enter_context(FFV1Writer(root / (name + ".mkv"), *size))
                       for name, size in SIZES.items()}

            def collect(frame):
                snapshot = active_world.get_snapshot()
                if snapshot.frame != frame:
                    raise ValueError("Native snapshot differs from tick frame")
                time_s = float(snapshot.timestamp.elapsed_seconds)
                if not math.isfinite(time_s):
                    raise ValueError("Finite original Native time required")
                for name in SIZES:
                    image = _joined_image(queues[name], frame)
                    writers[name].write(bytes(image.raw_data))
                frame_map.append(frame, time_s)
                frame_times[frame] = time_s
                return {name: frame for name in SIZES}

            yield collect

        def write_source(record):
            body_stream.write(json.dumps(record, allow_nan=False) + "\n")
            bodies = record["actor_sources"]
            time_s = frame_times.pop(record["native_frame"])
            if original_capture is not None:
                original_capture.capture(record["native_frame"], time_s)
            crossing = {"frame": record["native_frame"],
                        "time_s": time_s,
                        "ego": bodies["ego"], "other": bodies["other"],
                        "ego_vertices_m": bodies["ego"]["body_vertices_xy_m"]}
            crossing_stream.write(json.dumps(crossing, allow_nan=False) + "\n")
            stop = {"frame": crossing["frame"], "time_s": crossing["time_s"],
                    "ego": _stop_state(bodies["ego"], polygon),
                    "other": _stop_state(bodies["other"], polygon)}
            stop_stream.write(json.dumps(stop, allow_nan=False) + "\n")
            if signal_stream is not None:
                signal = {"frame": crossing["frame"], "time_s": crossing["time_s"],
                          "native_signal_id": signal_ids["ego"],
                          "state": _native_state(governed_lights["ego"]),
                          "other_native_signal_id": signal_ids["other"],
                          "other_state": _native_state(governed_lights["other"])}
                signal_stream.write(json.dumps(signal, allow_nan=False) + "\n")

        try:
            receipt = run_candidate_opposite_turn(
                world, carla, site, turning_role, blueprints, transforms,
                release_frames, target_speeds_mps, frames,
                lambda frame: None, write_source, camera_factory=camera_factory,
                lookahead_m=lookahead_m)
        except ValueError as error:
            prefix = "Native actor spawn failed: "
            if str(error).startswith(prefix):
                role = str(error)[len(prefix):]
                (root / "spawn_attempt.json").write_text(json.dumps({
                    "format": "worker-c125751-opposite-spawn-attempt-v1",
                    "selected_case_id": case_id,
                    "attempted_role": role,
                    "approach_spawn_succeeded": False,
                    "observation": "Native try_spawn_actor returned None",
                    "site_review_sha256": reviewed["packet_sha256"] if client is not None else None,
                    "physical_or_legal_acceptance_claimed": False},
                    allow_nan=False) + "\n")
            raise
    return receipt


DEVICE_SOURCES = ("signal_context.json", "signal_history.jsonl", "stop_context.json", "stop_history.jsonl")

def analyze_device_sources(root):
    """Join captured stop and governed-light observations to original frames.

    A candidate signal inventory names actors and lanes; official device status
    and statutory governance remain independent review judgments.
    """
    import hashlib
    import turn_context
    root = Path(root)
    base = turn_context.analyze(root)
    paths = {name: root / name for name in DEVICE_SOURCES}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError("Missing opposite-turn device source: " + name)
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    result_path = root / "result.json"
    if result_path.is_file():
        recorded = json.loads(result_path.read_text()).get("source_evidence_hashes", {})
        for name in DEVICE_SOURCES:
            if recorded.get(name) != hashes[name]:
                raise ValueError("Opposite-turn device source differs from saved result: " + name)
    context = json.loads(paths["signal_context.json"].read_text())
    if (context.get("intersection_id") != base["intersection_id"] or
            not context.get("native_map_id") or
            not context.get("device_inventory_source") or
            context.get("review_status") != "candidate_only"):
        raise ValueError("Sourced candidate signal context required")
    ids = [context.get("native_signal_id"), context.get("other_native_signal_id")]
    if any(type(value) is not int or value <= 0 for value in ids) or ids[0] == ids[1]:
        raise ValueError("Distinct governed Native signal identities required")
    governed = {"ego": (context.get("governed_road_id"), context.get("governed_lane_id")),
                "other": (context.get("other_governed_road_id"), context.get("other_governed_lane_id"))}
    if any(any(type(value) is not int for value in pair) for pair in governed.values()):
        raise ValueError("Sourced governed approach lanes required")
    stop_context = json.loads(paths["stop_context.json"].read_text())
    road_context = json.loads((root / "road_geometry.json").read_text())
    polygon = Polygon(road_context.get("intersection_polygon_xy_m", []))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Sourced crossing polygon required to verify original stop observations")
    references = stop_context.get("selected_references")
    if (stop_context.get("intersection_id") != base["intersection_id"] or
            stop_context.get("review_status") != "candidate_only" or
            not isinstance(references, dict) or set(references) != {"ego", "other"}):
        raise ValueError("Sourced candidate stop context required")
    for role, reference in references.items():
        if (not isinstance(reference, dict) or
                reference.get("kind") not in ("marked_stop_line", "near_side_crosswalk", "nearest_view_point") or
                not reference.get("geometry_source") or not reference.get("reference_review_source")):
            raise ValueError("Sourced candidate stop reference required: " + role)
        segment = reference.get("segment_xy_m")
        if (not isinstance(segment, list) or len(segment) != 2 or
                any(not isinstance(point, list) or len(point) != 2 or
                    any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
                    for point in segment) or math.dist(segment[0], segment[1]) <= 0):
            raise ValueError("Finite nondegenerate stop reference segment required: " + role)
    frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines() if line.strip()]
    crossing = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines() if line.strip()]
    signals = [json.loads(line) for line in paths["signal_history.jsonl"].read_text().splitlines() if line.strip()]
    stops = [json.loads(line) for line in paths["stop_history.jsonl"].read_text().splitlines() if line.strip()]
    if not (len(frames) >= 2 and len(frames) == len(crossing) == len(signals) == len(stops)):
        raise ValueError("Complete original signal, stop, crossing and camera histories required")
    allowed = {"Red", "Yellow", "Green", "Off", "Unknown"}
    observations = []
    for index, (frame, body, signal, stop) in enumerate(zip(frames, crossing, signals, stops)):
        native_frame = frame.get("carla_frame")
        native_time = frame.get("time_s")
        if (frame.get("video_frame") != index or
                any(row.get("frame") != native_frame or row.get("time_s") != native_time
                    for row in (body, signal, stop))):
            raise ValueError("Opposite-turn device original-frame join failed")
        if (signal.get("native_signal_id") != ids[0] or
                signal.get("other_native_signal_id") != ids[1] or
                signal.get("state") not in allowed or signal.get("other_state") not in allowed):
            raise ValueError("Original governed signal identity/state differs from context")
        for role in ("ego", "other"):
            sample = stop.get(role)
            actor = body.get(role)
            if (not isinstance(sample, dict) or not isinstance(actor, dict) or
                    type(sample.get("speed_mps")) not in (int, float) or
                    not math.isfinite(sample["speed_mps"]) or sample["speed_mps"] < 0 or
                    type(sample.get("body_inside_crossing")) is not bool or
                    sample.get("native_road_id") != actor.get("native_road_id") or
                    sample.get("native_lane_id") != actor.get("native_lane_id")):
                raise ValueError("Original stop observation differs from body source: " + role)
            velocity = actor.get("velocity_xyz_mps")
            if (not isinstance(velocity, list) or len(velocity) != 3 or
                    any(type(value) not in (int, float) or not math.isfinite(value)
                        for value in velocity) or
                    type(actor.get("speed_mps")) not in (int, float) or
                    not math.isclose(actor["speed_mps"], math.hypot(*velocity),
                                     rel_tol=1e-9, abs_tol=1e-9)):
                raise ValueError("Original body speed differs from velocity source: " + role)
            expected_stop = _stop_state(actor, polygon)
            if (not math.isclose(sample["speed_mps"], expected_stop["speed_mps"],
                                 rel_tol=1e-9, abs_tol=1e-9) or
                    sample.get("front_xy_m") != expected_stop["front_xy_m"] or
                    sample["body_inside_crossing"] != expected_stop["body_inside_crossing"]):
                raise ValueError("Original stop observation differs from body geometry: " + role)
            if index == 0 and (actor["native_road_id"], actor["native_lane_id"]) != governed[role]:
                raise ValueError("Original approach differs from governed signal lane: " + role)
        observations.append({"frame": native_frame, "time_s": native_time,
                             "ego_signal_state": signal["state"],
                             "other_signal_state": signal["other_state"],
                             "ego_speed_mps": stop["ego"]["speed_mps"],
                             "other_speed_mps": stop["other"]["speed_mps"],
                             "ego_body_inside_crossing": stop["ego"]["body_inside_crossing"],
                             "other_body_inside_crossing": stop["other"]["body_inside_crossing" ]})
    return {"format": "worker-c125751-opposite-device-sources-v1",
            "intersection_id": base["intersection_id"],
            "native_map_id": context["native_map_id"],
            "source_hashes": {**base["source_hashes"], **hashes},
            "native_signal_ids": {"ego": ids[0], "other": ids[1]},
            "selected_stop_references": references,
            "observations": observations,
            "official_device_judgment": "unresolved",
            "governance_judgment": "unresolved",
            "physical_acceptance_claimed": False}


def analyze_candidate_opposite_entry(root):
    """Measure paired body entries from saved candidate sources, without priority claims.

    The selected signal-case entry analyzer requires a lateral right-side approach.
    Opposing approaches have no such side, so this path measures entry order only.
    """
    import hashlib
    root = Path(root)
    device = analyze_device_sources(root)
    route_context = json.loads((root / "turn_route_context.json").read_text())
    road_context = json.loads((root / "road_geometry.json").read_text())
    from opposite_turn_construction import check_routes
    body_path = root / "body_history.jsonl"
    if not body_path.is_file():
        raise ValueError("Missing original opposite-turn body history")
    body_hash = hashlib.sha256(body_path.read_bytes()).hexdigest()
    result_path = root / "result.json"
    if result_path.is_file():
        recorded_hash = json.loads(result_path.read_text()).get("source_evidence_hashes", {}).get("body_history.jsonl")
        if recorded_hash != body_hash:
            raise ValueError("Opposite-turn body source differs from saved result")
    frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines() if line.strip()]
    crossing = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines() if line.strip()]
    bodies = [json.loads(line) for line in body_path.read_text().splitlines() if line.strip()]
    if len(bodies) != len(frames) or len(crossing) != len(frames):
        raise ValueError("Complete original opposite-turn body/camera history required")
    polygon = Polygon(road_context["intersection_polygon_xy_m"])
    first = {"ego": None, "other": None}
    turning_role = None
    for index, (frame, recorded, crossed) in enumerate(zip(frames, bodies, crossing)):
        native_frame = frame["carla_frame"]
        if (recorded.get("native_frame") != native_frame or
                recorded.get("frame_index") != index or
                recorded.get("actor_sources") != {role: crossed.get(role) for role in ("ego", "other")} or
                not isinstance(recorded.get("camera_source_frames"), dict) or
                set(recorded["camera_source_frames"]) != set(SIZES) or
                any(value != native_frame for value in recorded["camera_source_frames"].values())):
            raise ValueError("Opposite-turn body/camera original-frame join failed")
        role = recorded.get("turning_role")
        if role not in ("ego", "other") or (turning_role is not None and role != turning_role):
            raise ValueError("Stable opposite-turn turning role required")
        turning_role = role
        for party in ("ego", "other"):
            vertices = crossed[party].get("body_vertices_xy_m")
            if (not isinstance(vertices, list) or len(vertices) < 4 or
                    any(not isinstance(point, list) or len(point) != 2 or
                        any(type(value) not in (int, float) or not math.isfinite(value)
                            for value in point) for point in vertices)):
                raise ValueError("Complete finite original body vertices required: " + party)
            inside = MultiPoint(vertices).convex_hull.intersects(polygon)
            if index == 0 and inside:
                raise ValueError("Opposite-turn original body starts inside crossing: " + party)
            if first[party] is None and inside:
                first[party] = {"frame": native_frame, "time_s": frame["time_s"]}
    if not all(first.values()):
        raise ValueError("Both opposite-turn original body entries required")
    if route_context.get("intersection_id") != road_context.get("intersection_id"):
        raise ValueError("Opposite-turn route and crossing identities differ")
    geometry = check_routes(route_context.get("routes"), turning_role,
                            road_context["intersection_polygon_xy_m"])
    from stop_measurements import analyze as measure_stop
    stop_order = measure_stop(root, {"intersection_id": road_context["intersection_id"],
                                    "first_body_entry": first})
    device_by_frame = {row["frame"]: row for row in device["observations"]}
    signal_at_entry = {
        party: {"frame": first[party]["frame"],
                "time_s": first[party]["time_s"],
                "native_signal_id": device["native_signal_ids"][party],
                "native_state": device_by_frame[first[party]["frame"]][party + "_signal_state"]}
        for party in ("ego", "other")}
    return {"format": "worker-c125751-opposite-entry-candidate-v1",
            "intersection_id": road_context["intersection_id"],
            "turning_role": turning_role,
            "first_body_entry": first,
            "turning_minus_other_entry_time_s": first[turning_role]["time_s"] -
                first["other" if turning_role == "ego" else "ego"]["time_s"],
            "construction_geometry": geometry,
            "signal_at_body_entry": signal_at_entry,
            "stop_order": stop_order,
            "source_hashes": {**device["source_hashes"], **stop_order["sources"],
                              "body_history.jsonl": body_hash},
            "official_device_judgment": "unresolved",
            "statutory_exception_judgment": "unresolved",
            "physical_acceptance_claimed": False}


def finalize_candidate_opposite_turn(attempt, output):
    """Finalize saved opposing-turn candidate sources without a legal verdict."""
    import hashlib
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain prior opposite-turn finalization; choose a fresh attempt")
    required = ("config.json", "road_geometry.json", "turn_route_context.json",
                "body_history.jsonl", "crossing_history.jsonl", "signal_context.json",
                "signal_history.jsonl", "stop_context.json", "stop_history.jsonl",
                "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl",
                *(name + ".mkv" for name in SIZES))
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required opposite-turn source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case = config.get("selected_case_id")
    if (config.get("law_id") != "NRS-484B-250-2" or
            config.get("cell_id") != "C125751" or
            case != "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__opposite_left_turn" or
            config.get("turning_role") not in ("ego", "other") or
            not isinstance(config.get("recording_description"), dict)):
        raise ValueError("Exact C125751 opposing-turn candidate config required")
    from opposite_site_probe import verify_opposite_site_packet
    reviewed = verify_opposite_site_packet(config, attempt)
    packet_path = Path(reviewed["packet_path"]).resolve()
    if not packet_path.is_relative_to(attempt.resolve()):
        raise ValueError("Retained opposite-turn site packet required inside attempt")
    packet_name = packet_path.relative_to(attempt.resolve()).as_posix()
    for name in ("road_geometry.json", "turn_route_context.json",
                 "stop_context.json", "signal_context.json"):
        context = json.loads((attempt / name).read_text())
        if context.get("site_review_sha256") != reviewed["packet_sha256"]:
            raise ValueError("Saved opposite-turn context differs from reviewed site packet: " + name)
    required = (*required, packet_name)
    entry = analyze_candidate_opposite_entry(attempt)
    if entry["turning_role"] != config["turning_role"]:
        raise ValueError("Saved turning role differs from exact config")
    def rows(name):
        return [json.loads(line) for line in (attempt / name).read_text().splitlines() if line.strip()]
    frames, trace, evidence = (rows(name) for name in
                               ("video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl"))
    if not (len(frames) >= 2 and len(frames) == len(trace) == len(evidence)):
        raise ValueError("Complete original trace/evidence frame join required")
    for mapped, motion, observed in zip(frames, trace, evidence):
        if (motion.get("frame") != mapped["carla_frame"] or
                observed.get("original_frame") != mapped["carla_frame"] or
                motion.get("time_s") != mapped["time_s"] or
                observed.get("recording_time_s") != mapped["time_s"]):
            raise ValueError("Original trace/evidence frame join failed")
    channels = attempt / "channels"
    channels.mkdir()
    signal = rows("signal_history.jsonl")
    stops = rows("stop_history.jsonl")
    with (channels / "signal_state.jsonl").open("x") as stream:
        for row in signal:
            stream.write(json.dumps({"time_s": row["time_s"], "value": {
                "frame": row["frame"], "native_signal_id": row["native_signal_id"],
                "native_state": row["state"],
                "other_native_signal_id": row["other_native_signal_id"],
                "other_native_state": row["other_state"]}}, allow_nan=False) + "\n")
    with (channels / "stop_state.jsonl").open("x") as stream:
        for row in stops:
            stream.write(json.dumps({"time_s": row["time_s"], "value": {
                "frame": row["frame"], "ego": row["ego"], "other": row["other"]}},
                allow_nan=False) + "\n")
    (channels / "entry_context.json").write_text(json.dumps({
        "entry_context": entry}, indent=2, allow_nan=False) + "\n")
    sources = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
               for name in required}
    result = {"case_id": case,
        "measured_values": {"turning_minus_other_entry_time_s":
                            entry["turning_minus_other_entry_time_s"],
                            "signal_at_body_entry": entry["signal_at_body_entry"]},
        "target_checks": [{"target": "opposing_left_turn_body_entries",
            "requested": True, "measured": True,
            "method": "original paired body/camera/source-route join", "tolerance": 0,
            "matched": True, "physical_cause_confirmed": False,
            "cause_evidence": ["body_history.jsonl", "crossing_history.jsonl",
                               "video_frames.jsonl", "turn_route_context.json"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved opposing-turn sources measured; physical/legal review pending",
        "physical_failure_flags": ["official device and statutory exception judgments unresolved"],
        "trace_reference": "trace.jsonl", "video_references": [name + ".mkv" for name in SIZES],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": name, "unit": "structured record",
                                "reference": "channels/" + name + ext}
                               for name, ext in (("signal_state", ".jsonl"),
                                                 ("stop_state", ".jsonl"),
                                                 ("entry_context", ".json"))],
        "source_evidence_hashes": sources,
        "capture_evidence_sha256": sources["capture/evidence.jsonl"],
        "realized_observables": {}}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    output.write_text(json.dumps({
        "format": "worker-c125751-opposite-turn-saved-analysis-v1",
        "case_id": case, "measurements": entry,
        "source_evidence_hashes": sources,
        "physical_acceptance_claimed": False,
        "legal_acceptance_claimed": False}, indent=2, allow_nan=False) + "\n")
    return entry


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    finalize_candidate_opposite_turn(args.attempt, args.output)

