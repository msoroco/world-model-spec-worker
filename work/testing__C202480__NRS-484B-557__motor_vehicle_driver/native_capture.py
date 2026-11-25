"""Acquire one complete, synchronized Native rail-stop attempt.

The four camera movies, frame map, vehicle footprint, and motion history all
come from the same post-tick world snapshot. Commands are retained separately.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from native_control import RailApproachController
from rail_stop_audit import audit_saved_file

VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
FRAMES = 900
PIXEL_SAMPLE_FRAMES = (0, 450, 899)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n",
                    encoding="utf-8")


def _footprint(ego) -> list[list[float]]:
    vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
    if len(vertices) != 8:
        raise ValueError("original ego bounding box must have eight vertices")
    xy = {(float(vertex.x), float(vertex.y)) for vertex in vertices}
    if len(xy) != 4 or any(not math.isfinite(v) for point in xy for v in point):
        raise ValueError("original ego footprint is incomplete or nonfinite")
    return [[x, y] for x, y in sorted(xy)]


def _open_encoders(attempt: Path, factory=subprocess.Popen):
    encoders = {}
    try:
        for name, width, height in VIEWS:
            path = attempt / f"{name}.mkv"
            if path.exists():
                raise ValueError("retain previous original video")
            command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                       "-n", "-f", "rawvideo", "-pixel_format", "bgra",
                       "-video_size", f"{width}x{height}", "-framerate", "20",
                       "-i", "pipe:0", "-an", "-c:v", "ffv1", "-pix_fmt", "bgra",
                       str(path)]
            encoders[name] = factory(command, stdin=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL)
        return encoders
    except BaseException:
        for encoder in encoders.values():
            if encoder.stdin:
                encoder.stdin.close()
            encoder.wait(timeout=180)
        raise


def _close_encoders(encoders: dict) -> dict[str, int]:
    codes = {}
    for name, encoder in encoders.items():
        if encoder.stdin and not encoder.stdin.closed:
            encoder.stdin.close()
        codes[name] = encoder.wait(timeout=180)
    return codes


def capture(world, scene: dict, camera, attempt: Path, case: dict,
            control_factory, *, encoder_factory=subprocess.Popen) -> dict:
    """Record exactly 45 seconds at 20 Hz, rejecting any missing source join."""
    from worker_exchange.native_output import FrameMap

    attempt = Path(attempt)
    attempt.mkdir(parents=True, exist_ok=True)
    for name in ("trace.jsonl", "video_frames.jsonl", "rail-stop-packet.json",
                 "native-ego-kinematics.json", "native-ego-footprint.json"):
        if (attempt / name).exists():
            raise ValueError("retain previous original acquisition")
    packet = scene["packet"]
    geometry = json.loads((Path(packet["_site_dir"]) /
                           packet["sources"]["crossing_geometry"]["path"]).read_text())
    rails = geometry.get("nearest_track_rails")
    if not isinstance(rails, list) or not rails:
        raise ValueError("reviewed nearest-track rail lines required")
    controller = RailApproachController(
        scene["ego"], packet["_rail_xy"], packet["_normal"],
        packet["ego_longitudinal_half_extent_m"], case["planned_stop_body_gap_ft"],
        control_factory, rolling=case["stop_behavior"] == "rolling",
        depart_on_conflict=case["departure_context"] == "crossing_conflict")
    encoders = _open_encoders(attempt, encoder_factory)
    motion, footprint, camera_joins, conflict_history = [], [], [], []
    previous_time = previous_frame = None
    error = None
    try:
        with FrameMap(attempt / "video_frames.jsonl") as frame_map, \
                (attempt / "trace.jsonl").open("x", encoding="utf-8") as trace, \
                (attempt / "control-requests.jsonl").open("x", encoding="utf-8") as controls:
            for index in range(FRAMES):
                # The conflict signal is a control input only. Independent
                # processing must measure the actual original scene.
                command = controller.step(case["departure_context"] == "clear_approach")
                if scene.get("conflict_actor") is not None:
                    scene["conflict_actor"].apply_control(control_factory(
                        throttle=packet["_conflict"]["throttle"], brake=0.0))
                frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != frame or (previous_frame is not None and frame != previous_frame + 1):
                    raise ValueError("Native world frames missing or out of order")
                timestamp = float(snapshot.timestamp.elapsed_seconds)
                if not math.isfinite(timestamp) or (previous_time is not None and
                        abs(timestamp - previous_time - .05) > .005):
                    raise ValueError("Native world timestamps are not 20 Hz")
                images = camera.await_frame(frame, timestamp)
                if set(images) != {name for name, _, _ in VIEWS}:
                    raise ValueError("four original camera frames required")
                for name, width, height in VIEWS:
                    image = images[name]
                    if image["frame"] != frame or image["width"] != width or image["height"] != height:
                        raise ValueError("original camera identity or size differs")
                    source = camera.output_root / image["raw_bgra"]
                    pixels = source.read_bytes()
                    if len(pixels) != width * height * 4 or _sha(pixels) != image["sha256"]:
                        raise ValueError("original camera pixels differ before encoding")
                    written = encoders[name].stdin.write(pixels)
                    if written != len(pixels):
                        raise ValueError("original camera encoder short write")
                    if index in PIXEL_SAMPLE_FRAMES:
                        png = attempt / f"original-{name}-{index:03d}.png"
                        if png.exists():
                            raise ValueError("retain previous original pixel sample")
                        subprocess.run([
                            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-f", "rawvideo", "-pixel_format", "bgra",
                            "-video_size", f"{width}x{height}", "-i", "pipe:0",
                            "-frames:v", "1", str(png)], input=pixels,
                            check=True, stdout=subprocess.DEVNULL, timeout=60)
                    # The lossless encoded original remains in the attempt; raw
                    # callback scratch is removed only after its bytes are joined.
                    source.unlink()
                camera_joins.append({"frame": index, "source_frame": frame,
                                     "cameras": {name: {
                                         "source_video": name + ".mkv",
                                         "original_bgra_sha256": images[name]["sha256"],
                                         "frame": frame,
                                         "width": images[name]["width"],
                                         "height": images[name]["height"]}
                                         for name, _, _ in VIEWS}})
                velocity = scene["ego"].get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                if not math.isfinite(speed):
                    raise ValueError("nonfinite original vehicle speed")
                elapsed = index / 20
                row = {"frame": index, "source_frame": frame,
                       "elapsed_s": elapsed, "speed_mps": speed}
                body = {"frame": index, "source_frame": frame,
                        "body_corners_xy_m": _footprint(scene["ego"])}
                motion.append(row)
                footprint.append(body)
                if scene.get("conflict_actor") is not None:
                    actor = scene["conflict_actor"]
                    conflict_velocity = actor.get_velocity()
                    conflict_history.append({
                        "frame": index, "source_frame": frame,
                        "body_corners_xy_m": _footprint(actor),
                        "speed_mps": math.sqrt(conflict_velocity.x**2 +
                                                conflict_velocity.y**2 +
                                                conflict_velocity.z**2)})
                mapped = frame_map.append(frame, timestamp)
                if mapped["video_frame"] != index:
                    raise ValueError("original video frame identity differs")
                location = scene["ego"].get_location()
                heading = float(scene["ego"].get_transform().rotation.yaw)
                trace.write(json.dumps({"frame": frame, "time_s": timestamp,
                                        "position": {"x": float(location.x),
                                                     "y": float(location.y),
                                                     "z": float(location.z)},
                                        "position_m": [float(location.x), float(location.y),
                                                       float(location.z)],
                                        "heading_deg": heading,
                                        "speed_mps": speed,
                                        "speed_mph": speed / .44704,
                                        "velocity_mps": [float(velocity.x),
                                                         float(velocity.y),
                                                         float(velocity.z)],
                                        "control": command}, allow_nan=False) + "\n")
                controls.write(json.dumps({"frame": frame, "time_s": timestamp,
                                           **command}, allow_nan=False) + "\n")
                previous_frame, previous_time = frame, timestamp
    except BaseException as exc:
        error = exc
    codes = _close_encoders(encoders)
    if error is not None:
        raise error
    if any(code != 0 for code in codes.values()) or len(motion) != FRAMES:
        raise ValueError("original camera encoding or 900-frame acquisition incomplete")
    _write_json(attempt / "native-ego-kinematics.json", motion)
    _write_json(attempt / "native-ego-footprint.json", footprint)
    if scene.get("conflict_actor") is not None:
        _write_json(attempt / "native-conflict-history.json", conflict_history)
    shutil.copyfile(Path(packet["_site_dir"]) /
                    packet["sources"]["crossing_geometry"]["path"],
                    attempt / "native-crossing-geometry.json")
    authority = packet["_authority"]
    shutil.copyfile(Path(packet["_site_dir"]) /
                    packet["sources"]["crossing_authority"]["path"],
                    attempt / "native-authority-record.json")
    _write_json(attempt / "native-stop-device.json", {
        "device_type": authority["device_type"], "device_governs": authority["device_governs"],
        "sign_landmark_id": authority["sign_landmark_id"]})
    sources = {}
    for key, name in (("native_crossing_geometry", "native-crossing-geometry.json"),
                      ("native_authority_record", "native-authority-record.json"),
                      ("native_stop_device", "native-stop-device.json"),
                      ("native_ego_kinematics", "native-ego-kinematics.json"),
                      ("native_ego_footprint", "native-ego-footprint.json")):
        sources[key] = {"path": name, "sha256": _sha((attempt / name).read_bytes())}
    if scene.get("conflict_actor") is not None:
        name = "native-conflict-history.json"
        sources["native_conflict_history"] = {"path": name,
                                               "sha256": _sha((attempt / name).read_bytes())}
    samples = [dict(motion[i], **footprint[i]) for i in range(FRAMES)]
    saved_packet = {"sources": sources, "nearest_track_rails": rails,
                    "context": {"crossing_type": authority["crossing_type"],
                                "designation_authority": authority["designation_authority"],
                                "dot_approval_source": authority.get("dot_approval_source"),
                                "device_type": authority["device_type"],
                                "device_governs": authority["device_governs"],
                                "actor": "motor_vehicle_driver"}, "samples": samples,
                    "conflict_samples": conflict_history if conflict_history else None,
                    "conflict_actor_present": scene.get("conflict_actor") is not None}
    _write_json(attempt / "rail-stop-packet.json", saved_packet)
    _write_json(attempt / "camera-frame-joins.json", camera_joins)
    _write_json(attempt / "pixel-sample-inventory.json", {
        "format": "original-camera-pixel-samples",
        "frames": list(PIXEL_SAMPLE_FRAMES),
        "samples": [{"camera": name, "video_frame": index,
                     "source_frame": camera_joins[index]["source_frame"],
                     "png": f"original-{name}-{index:03d}.png",
                     "original_bgra_sha256": camera_joins[index]["cameras"][name]["original_bgra_sha256"]}
                    for index in PIXEL_SAMPLE_FRAMES for name, _, _ in VIEWS]})
    measured = audit_saved_file(attempt / "rail-stop-packet.json")
    return {"frames": FRAMES, "encoder_exit_codes": codes,
            "rail_measurement": measured, "first_native_frame": motion[0]["source_frame"],
            "last_native_frame": motion[-1]["source_frame"],
            "physical_acceptance_claimed": False}
