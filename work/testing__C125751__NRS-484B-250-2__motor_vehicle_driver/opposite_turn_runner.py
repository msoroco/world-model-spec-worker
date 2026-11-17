"""Candidate opposite-turn capture loop for CPU and future Native site binding.

The caller supplies a frame-aligned camera collector and source writer. This
module does not mark a candidate site reviewed or create accepted media.
"""

import math
import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue
from shapely.geometry import Polygon

from camera_setup import SIZES, source_cameras
from camera_encoder import FFV1Writer
from capture_sources import _actor, _native_state, _stop_state
from opposite_turn_construction import (construct_opposite_turn_pair,
                                        command_opposite_turn_pair)


def run_candidate_opposite_turn(world, carla, site, turning_role, blueprints,
                                transforms, release_frames, target_speeds_mps,
                                frames, collect_camera_frames, write_source,
                                camera_factory=None):
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
                target_speeds_mps, turning_role)
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


def capture_candidate_media(output_dir, world, carla, site, turning_role,
                            blueprints, transforms, release_frames,
                            target_speeds_mps, frames, governed_lights=None):
    """Write four FFV1 sources, frame map and paired original actor records.

    This is a candidate capture path; the exact selected manifest, source site
    review, finalizer and independent delivery audit are separate requirements.
    """
    root = Path(output_dir)
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError("Fresh existing candidate capture directory required")
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
        "review_status": "candidate_only"}, allow_nan=False) + "\n")
    (root / "turn_route_context.json").write_text(json.dumps({
        "intersection_id": junction_id, "routes": site["routes"],
        "approach_geometry_source": site["approach_geometry_source"],
        "turn_intention_source": "Native route candidate; original trajectory requires review",
        "review_status": "candidate_only"}, allow_nan=False) + "\n")
    (root / "stop_context.json").write_text(json.dumps({
        "intersection_id": junction_id,
        "selected_references": references,
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

        @contextmanager
        def camera_factory(active_world, actors):
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
            crossing = {"frame": record["native_frame"],
                        "time_s": frame_times.pop(record["native_frame"]),
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

        receipt = run_candidate_opposite_turn(
            world, carla, site, turning_role, blueprints, transforms,
            release_frames, target_speeds_mps, frames,
            lambda frame: None, write_source, camera_factory=camera_factory)
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

