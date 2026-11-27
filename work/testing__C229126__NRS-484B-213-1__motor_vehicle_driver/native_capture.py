"""One synchronized original Native episode for a reviewed passing construction.

The live caller owns exclusive CARLA access. This module never launches a server.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import threading
from pathlib import Path
import shutil

from native_scene import CAMERAS, PassScene


def _write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _state(actor, axis, origin):
    transform = actor.get_transform()
    bounds = actor.bounding_box.get_world_vertices(transform)
    points = [(v.x-origin[0], v.y-origin[1]) for v in bounds]
    stations = [x*axis[0]+y*axis[1] for x, y in points]
    laterals = [-x*axis[1]+y*axis[0] for x, y in points]
    center = actor.get_location()
    velocity = actor.get_velocity()
    return {"actor_id": actor.id, "vehicle": True,
            "station_m": (center.x-origin[0])*axis[0]+(center.y-origin[1])*axis[1],
            "front_station_m": max(stations), "rear_station_m": min(stations),
            "centerline_signed_body_edge_m": max(laterals),
            "speed_mps": math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
            "lateral_m": -(center.x-origin[0])*axis[1]+(center.y-origin[1])*axis[0],
            "body_vertices_xy_m": [[v.x, v.y] for v in bounds]}


def _ray(scene, ego, axis, distance_m=230.0):
    carla = scene.carla
    loc = ego.get_location()
    start = carla.Location(x=loc.x, y=loc.y, z=loc.z+1.4)
    # A forward left-side ray is an observer proxy, not a driver-eye claim.
    end = carla.Location(x=start.x+axis[0]*distance_m-axis[1]*2,
                         y=start.y+axis[1]*distance_m+axis[0]*2, z=start.z)
    hits = list(scene.world.cast_ray(start, end))
    if hits:
        hit = hits[0]
        point = hit.location
        length = math.sqrt((point.x-start.x)**2+(point.y-start.y)**2+(point.z-start.z)**2)
        kind = "vehicle" if str(getattr(hit, "label", "")).lower().endswith("vehicles") else "opaque_obstacle"
        return {"clear_distance_m": length, "censored": False, "hit_kind": kind,
                "hit_actor_id": getattr(hit, "actor_id", None),
                "hit_label": str(getattr(hit, "label", ""))}
    return {"clear_distance_m": distance_m, "censored": True, "hit_kind": "range_limit"}


def _encoder(path, width, height):
    return subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-f", "rawvideo",
                             "-pix_fmt", "bgra", "-s", f"{width}x{height}",
                             "-r", "20", "-i", "pipe:0", "-an", "-c:v", "libx264rgb",
                             "-preset", "ultrafast", "-qp", "0", "-pix_fmt", "rgb24",
                             "-y", str(path)], stdin=subprocess.PIPE,
                            stderr=subprocess.PIPE)


def capture(client, packet, case_id, source_root, output, *, carla_module=None,
            scene_factory=PassScene, graph_factory=None):
    from worker_exchange.native_output import FrameMap, write_result, seal_capture
    output = Path(output)
    if not output.is_dir() or any((output / name).exists() for name in
                                 ("trace.jsonl", "video_frames.jsonl", "capture-seal.json", "result.json")):
        raise ValueError("fresh materialized Native attempt required")
    scene = scene_factory(client, packet, case_id, source_root, carla_module=carla_module)
    encoders = {}
    cameras = {}
    condition = threading.Condition()
    pending = {}
    graph = None
    original_count = 0
    release = None
    try:
        setup = scene.begin()
        retained = output / "reviewed-sources"
        retained.mkdir(exist_ok=False)
        for role, ref in scene.bound_sources.items():
            shutil.copyfile(ref["path"], retained / (role + ".source"))
            if _hash(retained / (role + ".source")) != ref["sha256"]:
                raise ValueError("reviewed source changed during retention")
        axis = packet["road"]["forward_unit_xy"]
        origin = packet["road"]["centerline_origin_xy"]
        if graph_factory is None:
            from pipeline_capture import PipelineCapture
            graph_factory = PipelineCapture
        graph = graph_factory(client, scene.actors["ego"], output, case_id)
        for name in CAMERAS:
            item = packet["cameras"][name]
            encoders[name] = _encoder(output / f"{name}.mkv", item["width"], item["height"])
            def callback(image, view=name):
                with condition:
                    if view in pending.setdefault(image.frame, {}):
                        raise ValueError("duplicate original camera callback")
                    pending[image.frame][view] = image
                    condition.notify_all()
            scene.sensors[name].listen(callback)
        _write(output / "road-context.json", packet["road"])
        _write(output / "acquisition-provenance.json", {"provenance_kind": "native",
                "diagnostic_fixture": False, "case_id": case_id,
                "review_source_sha256": packet["review_source_sha256"],
                "source_bindings": scene.bound_sources})
        with FrameMap(output / "video_frames.jsonl") as frame_map, \
             (output / "trace.jsonl").open("x") as trace, \
             (output / "pass-history.jsonl").open("x") as history:
            last_time = None
            for index in range(packet["duration_s"]*20):
                step = scene.tick(index)
                world_frame = step["world_frame"]
                snapshot = scene.world.get_snapshot()
                timestamp = snapshot.timestamp.elapsed_seconds
                if last_time is not None and abs(timestamp-last_time-.05) > .002:
                    raise ValueError("Native 20 Hz timestamp discontinuity")
                last_time = timestamp
                with condition:
                    ready = condition.wait_for(lambda: set(pending.get(world_frame, {})) == set(CAMERAS), timeout=15)
                    if not ready:
                        raise ValueError("missing synchronized original camera callback")
                    images = pending.pop(world_frame)
                for name in CAMERAS:
                    image = images[name]
                    spec = packet["cameras"][name]
                    if (image.width, image.height) != (spec["width"], spec["height"]):
                        raise ValueError("original camera dimensions differ")
                    encoders[name].stdin.write(bytes(image.raw_data))
                frame_map.append(world_frame, timestamp, camera_frames={name: world_frame for name in CAMERAS})
                participants = {role: dict(_state(scene.actors[role], axis, origin),
                                           direction=packet["actors"][role]["direction"])
                                for role in packet["actors"]}
                ray = _ray(scene, scene.actors["ego"], axis)
                record = {"original_frame": index, "frame": world_frame,
                          "carla_frame": world_frame,
                          "time_s": timestamp, "actors": participants,
                          "left_side_rays": [ray], "commands": step["commands"]}
                history.write(json.dumps(record, sort_keys=True) + "\n")
                ego = participants["ego"]
                ego_transform = scene.actors["ego"].get_transform()
                ego_location = ego_transform.location
                trace.write(json.dumps({"video_frame": index, "frame": world_frame,
                                        "carla_frame": world_frame,
                                        "native_frame": world_frame, "time_s": timestamp,
                                        "position": {"x": ego_location.x,
                                                     "y": ego_location.y,
                                                     "z": ego_location.z},
                                        "heading_deg": ego_transform.rotation.yaw,
                                        "position_m": [ego["station_m"], ego["lateral_m"]],
                                        "speed_mps": ego["speed_mps"]}, sort_keys=True) + "\n")
                graph.capture(world_frame, timestamp)
                original_count += 1
        cameras = {}
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            code = process.wait()
            process.stderr.close()
            cameras[name] = {"path": f"{name}.mkv", "sha256": _hash(output / f"{name}.mkv"),
                             "exit_code": code}
            if code != 0:
                raise ValueError("original camera encoder failed: " + stderr.decode(errors="replace")[-500:])
        encoders.clear()
    except BaseException as exc:
        _write(output / "native-run-status.json", {"case_id": case_id,
                "errors": [type(exc).__name__ + ": " + str(exc)],
                "frames_captured": original_count,
                "physical_acceptance_claimed": False})
        raise
    finally:
        try:
            if graph is not None:
                graph.close()
            for process in encoders.values():
                if process.poll() is None:
                    process.kill()
                process.wait()
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.stderr and not process.stderr.closed:
                    process.stderr.close()
        finally:
            release = scene.close()
            _write(output / "owner-release.json", release)
    result = {"measured_values": {"original_frame_count": original_count},
              "target_checks": [{"target": "full_original_episode", "requested": packet["duration_s"]*20,
                                 "measured": original_count, "method": "continuous original CARLA frames",
                                 "tolerance": 0, "matched": original_count == packet["duration_s"]*20,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": "pass-history.jsonl; visual and physical review pending"}],
              "setup_confirmed": True, "behavior_attempted": True,
              "maneuver_completed": False, "termination_reason": "planned_duration",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [f"{name}.mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": packet["recording_description"],
              "recording_evidence": {"pass_history": "pass-history.jsonl",
                                     "road_context": "road-context.json"},
              "realized_observables": {"physical_review": "pending"}}
    write_result(output, result)
    _write(output / "native-result.json", result)
    seal = seal_capture(output, frames=original_count, restoration=release["restoration"],
                        errors=[], encoder_exit_codes={name: c["exit_code"] for name, c in cameras.items()},
                        context={"road": packet["road"], "case_id": case_id})
    return {"case_id": case_id, "original_frames": original_count,
            "capture_seal": seal["source_digest"], "physical_acceptance_claimed": False}
