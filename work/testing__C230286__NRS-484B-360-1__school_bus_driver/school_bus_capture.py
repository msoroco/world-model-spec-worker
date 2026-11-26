"""Capture 900 source-sealed Native school-bus frames and four lossless views."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from package_spec import AID, CAMERA_NAMES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n")


def capture(adapter, site, case, destination):
    destination = Path(destination).resolve()
    if destination.exists() or ".runtime-work" not in destination.parts or getattr(adapter, "native_attested", False) is not True:
        raise ValueError("attested original Native attempt belongs under fresh .runtime-work path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="school-bus-original-", dir=destination.parent))
    try:
        adapter.configure()
        adapter.spawn()
        folders = {name: stage / ("frames-" + name) for name in CAMERA_NAMES}
        for folder in folders.values():
            folder.mkdir()
        rows, mapping, trace = [], [], []
        prior = None
        for index in range(900):
            native_frame, native_time = adapter.tick()
            if type(native_frame) is not int or type(native_time) not in (float, int):
                raise ValueError("Native frame/time absent")
            if prior is not None and (native_frame != prior[0] + 1 or abs(native_time - prior[1] - .05) > .002):
                raise ValueError("Native 20 Hz frame/time continuity failed")
            prior = native_frame, native_time
            time_s = index / 20
            row = adapter.read(native_frame, time_s)
            if row.get("frame") != native_frame or row.get("time_s") != time_s or len(row.get("actor_ids", ())) != 1:
                raise ValueError("original Native bus readback absent")
            images = adapter.pixels(native_frame)
            if set(images) != set(CAMERA_NAMES):
                raise ValueError("four original cameras required")
            hashes = {}
            for name in CAMERA_NAMES:
                raw = images[name].get("png")
                if images[name].get("frame") != native_frame or not isinstance(raw, bytes) or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("camera frame or original pixels absent: " + name)
                (folders[name] / f"{index:04d}.png").write_bytes(raw)
                hashes[name] = hashlib.sha256(raw).hexdigest()
            row["native_frame"] = native_frame
            row["frame"] = index
            rows.append(row)
            mapping.append({"video_frame": index, "native_frame": native_frame,
                            "carla_frame": native_frame, "time_s": time_s,
                            "camera_png_sha256": hashes})
            position = row["bus_position_xyz_m"]
            trace.append({"frame": native_frame, "time_s": time_s,
                          "position_m": position,
                          "position": dict(zip(("x", "y", "z"), position)),
                          "heading_deg": row["bus_heading_deg"],
                          "speed_mps": row["bus_speed_mps"],
                          "speed_mph": row["bus_speed_mps"] / .44704})
        (stage / "video_frames.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in mapping))
        (stage / "trace.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in trace))
        history = {"source_kind": "original_native_actor_history", "assignment_id": AID,
                   "case_id": case, "reviewed_site_sha256": site["reviewed_site_sha256"],
                   "map_sha256": site["map_sha256"], "school_bus_classification": site["school_bus_classification"],
                   "driver_actor_id": site["driver_actor_id"], "bus_actor_id": rows[0]["actor_ids"][0],
                   "transport_direction": site["trip"]["direction"],
                   "transport_source": site["trip"]["source"],
                   "pupil_count": site["trip"]["pupil_count"],
                   "pupil_presence_source": site["trip"]["pupil_presence_source"],
                   "sidewalk_source": site["sidewalk"]["source_id"], "samples": rows}
        put(stage / "school-bus-history.json", history)
        active = [row["bus_speed_mps"] * 2.2369362920544 for row in rows if row["transporting_pupils_to_or_from_school"]]
        put(stage / "school-bus-measurement.json", {
            "maximum_active_transport_speed_mph": max(active, default=None),
            "active_transport_frame_count": len(active),
            "above_55_mph_observed": any(speed > 55 for speed in active),
            "maximum_all_speed_mph": max(row["bus_speed_mps"] * 2.2369362920544 for row in rows),
            "review_limit": "Original speed and source-joined pupil trip status require independent review; no legal verdict"})
        videos = {}
        for name, folder in folders.items():
            video = stage / (name + ".mkv")
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-framerate", "20",
                            "-i", str(folder / "%04d.png"), "-frames:v", "900",
                            "-c:v", "ffv1", str(video)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            videos[name] = {"path": video.name, "sha256": sha(video), "frame_count": 900}
            shutil.rmtree(folder)
        put(stage / "original-source-receipt.json", {
            "source_kind": "original_native_capture", "diagnostic_fixture": False,
            "case_id": case, "fps": 20, "frame_count": 900,
            "reviewed_site_sha256": site["reviewed_site_sha256"],
            "history_sha256": sha(stage / "school-bus-history.json"),
            "trace_sha256": sha(stage / "trace.jsonl"),
            "frame_map_sha256": sha(stage / "video_frames.jsonl"),
            "measurement_sha256": sha(stage / "school-bus-measurement.json"),
            "cameras": videos, "physical_acceptance": False, "legal_verdict": None})
        os.replace(stage, destination)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        adapter.cleanup()
