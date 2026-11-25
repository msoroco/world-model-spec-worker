"""Acquire original 20 Hz signal, path, weather and four camera histories.

The local adapter owns CARLA world/actor/sensor lifetimes. This module never
substitutes a diagnostic packet for an original scene observation.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

from PIL import Image

from native_site import validate
from signal_controller import request_right_signal
from native_capture_contract import CAMERAS, DIMENSIONS, FRAMES, STEP_S



def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _angle_from_start(start: float, current: float) -> float:
    return (current - start + 180.0) % 360.0 - 180.0


def _state(session) -> dict:
    value = session.read_ego_state()
    for key in ("x_m", "y_m", "heading_deg", "speed_m_s", "actor_id", "blueprint_id"):
        if key not in value:
            raise ValueError("missing original ego readback: " + key)
    if any(not math.isfinite(float(value[key])) for key in
           ("x_m", "y_m", "heading_deg", "speed_m_s")):
        raise ValueError("nonfinite original ego readback")
    return value


def capture(session, site: dict, site_sha256: str, case: dict, output: Path, *, frames: int = FRAMES) -> dict:
    """Capture with an adapter that exposes real CARLA readback each tick."""
    geometry = validate(site)
    if frames != FRAMES and not getattr(session, "diagnostic_test_only", False):
        raise ValueError("production Native capture requires 900 frames")
    if session.read_map_name() != site["map_name"]:
        raise ValueError("reviewed map differs from Native world")
    tag = case["case_id"].rsplit("__", 1)[-1]
    if case["target"]["weather_request"] not in ("clear", "rain"):
        raise ValueError("unsupported exact weather request")
    if case["target"]["signal_continuity_request"] not in ("continuous", "interrupt_then_resume"):
        raise ValueError("unsupported exact signal request")
    start = site["approach_start_xyz"]
    turn = site["turn_vertex_xyz"]
    outgoing = site["outgoing_target_xyz"]
    ego = session.spawn_ego(site["ego_blueprint_id"], start)
    if (str(ego["actor_id"]) != str(_state(session)["actor_id"])
            or _state(session)["blueprint_id"] != site["ego_blueprint_id"]):
        raise ValueError("spawned ego identity readback differs")
    session.set_weather(case["target"]["weather_request"])
    heading_start = math.degrees(math.atan2(turn[1] - start[1], turn[0] - start[0]))
    approach_length = geometry["approach_length_m"]
    ux = (turn[0] - start[0]) / approach_length
    uy = (turn[1] - start[1]) / approach_length
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    trace = output / "original-turn-signal.json"
    archives = {name: output / (name + ".png.zip") for name in CAMERAS}
    if trace.exists() or any(path.exists() for path in archives.values()):
        raise ValueError("original acquisition output already exists")
    streams = {}
    rows = []
    try:
        for name, path in archives.items():
            streams[name] = ZipFile(path, "x", compression=ZIP_STORED)
        previous = None
        for index in range(frames):
            before = _state(session)
            remaining = max(0.0, (turn[0] - before["x_m"]) * ux
                            + (turn[1] - before["y_m"]) * uy)
            turned = _angle_from_start(heading_start, float(before["heading_deg"])) <= -15.0
            target = outgoing if turned else turn
            session.command_drive(target)
            requested = request_right_signal(tag, remaining, turned,
                                             speed_m_s=float(before["speed_m_s"]))
            session.request_right_signal(requested)
            tick = session.tick()
            if type(tick.get("frame")) is not int or not math.isfinite(float(tick.get("time_s"))):
                raise ValueError("missing original tick identity")
            if previous is not None and (tick["frame"] != previous["frame"] + 1 or
                                         abs(tick["time_s"] - previous["time_s"] - STEP_S) > 1e-4):
                raise ValueError("original Native tick or 20 Hz clock gap")
            after = _state(session)
            if str(after["actor_id"]) != str(ego["actor_id"]):
                raise ValueError("original ego identity changed")
            delta = _angle_from_start(heading_start, float(after["heading_deg"]))
            course_change = delta <= -15.0
            weather = session.read_weather()
            if weather != case["target"]["weather_request"]:
                raise ValueError("original Native weather readback differs")
            row = {"frame": tick["frame"], "time_s": tick["time_s"],
                   "x_m": after["x_m"], "y_m": after["y_m"],
                   "heading_deg": after["heading_deg"],
                   "right_signal": session.read_right_signal(),
                   "requested_right_signal": requested,
                   "course_change": course_change,
                   "weather": weather, "actor_id": str(after["actor_id"]),
                   "camera_frames": {}}
            if type(row["right_signal"]) is not bool:
                raise ValueError("missing original right-signal readback")
            for name in CAMERAS:
                sample = session.read_camera(name, tick["frame"])
                if sample.get("frame") != tick["frame"] or not isinstance(sample.get("png_bytes"), bytes):
                    raise ValueError("original camera frame mismatch: " + name)
                data = sample["png_bytes"]
                with Image.open(BytesIO(data)) as image:
                    image.load()
                    if image.format != "PNG" or image.size != DIMENSIONS[name]:
                        raise ValueError("original camera dimensions differ: " + name)
                member = f"{tick['frame']:08d}.png"
                streams[name].writestr(member, data)
                row["camera_frames"][name] = {"member": member, "sha256": _sha(data)}
            rows.append(row)
            previous = tick
        for stream in streams.values():
            stream.close()
        streams.clear()
        context = {key: site[key] for key in ("highway_source", "district_source",
                   "frontage_source", "building_use_source", "loading_zone_source")}
        context.update({"district_kind": "business", "maneuver": "right_turn",
                        "weather_source": "original Native weather readback: " +
                                          case["target"]["weather_request"]})
        diagnostic = bool(getattr(session, "diagnostic_test_only", False))
        packet = {"format": "native-turn-signal-samples-v1",
                  "source_kind": "diagnostic_fixture" if diagnostic else "original_native",
                  "diagnostic_fixture": diagnostic, "case_id": case["case_id"],
                  "ego_actor": "motor_vehicle_driver", "ego_actor_id": str(ego["actor_id"]),
                  "context": context, "site_sha256": site_sha256,
                  "sampling_hz": 20, "frame_count": frames, "samples": rows,
                  "camera_archives": {name: {"path": path.name, "sha256": _sha(path.read_bytes()),
                                             "frame_count": frames, "dimensions": list(DIMENSIONS[name])}
                                      for name, path in archives.items()}}
        trace.write_text(json.dumps(packet, sort_keys=True) + "\n")
        return {"trace_path": trace.name, "trace_sha256": _sha(trace.read_bytes()),
                "frame_count": frames, "camera_archives": packet["camera_archives"],
                "original_capture_claimed": not diagnostic}
    except BaseException:
        for stream in streams.values():
            stream.close()
        for path in archives.values():
            path.unlink(missing_ok=True)
        trace.unlink(missing_ok=True)
        raise
