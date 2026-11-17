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
