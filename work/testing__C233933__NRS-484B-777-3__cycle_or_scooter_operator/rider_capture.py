"""Capture source-sealed 900-frame rider formation motion and four cameras."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from package_spec import AID, CAMERA_NAMES
from abreast import measure_original


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n")


def capture(adapter, site, case, destination):
    destination = Path(destination).resolve()
    need(not destination.exists() and ".runtime-work" in destination.parts,
         "original attempt belongs under .runtime-work")
    need(getattr(adapter, "native_attested", False) is True,
         "attested Native CARLA adapter required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="rider-original-", dir=destination.parent))
    try:
        adapter.configure()
        adapter.spawn()
        folders = {name: stage / ("frames-" + name) for name in CAMERA_NAMES}
        for folder in folders.values():
            folder.mkdir()
        rows, mapping, trace = [], [], []
        prior = None
        for index in range(900):
            frame, time_s = adapter.tick()
            need(type(frame) is int and type(time_s) in (float, int),
                 "original Native frame/time missing")
            if prior is not None:
                need(frame == prior[0] + 1 and abs(time_s - prior[1] - .05) <= .002,
                     "original Native 20 Hz cadence differs")
            prior = frame, time_s
            row = adapter.read(frame, time_s)
            need(row.get("frame") == frame and row.get("time_s") == time_s and
                 len(row.get("native_actor_ids", ())) == adapter.case.riders,
                 "original bicycle riders/frame missing")
            row["native_frame"] = frame
            row["original_frame"] = frame
            row["frame"] = index
            row["time_s"] = index / 20
            images = adapter.pixels(frame)
            need(set(images) == set(CAMERA_NAMES), "four original cameras required")
            hashes = {}
            for name in CAMERA_NAMES:
                raw = images[name].get("png")
                need(images[name].get("frame") == frame and isinstance(raw, bytes) and
                     raw.startswith(b"\x89PNG\r\n\x1a\n"),
                     "original camera frame or pixels missing: " + name)
                (folders[name] / f"{index:04d}.png").write_bytes(raw)
                hashes[name] = hashlib.sha256(raw).hexdigest()
            rows.append(row)
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "native_frame": frame, "time_s": index / 20,
                            "camera_png_sha256": hashes})
            position = row["ego_position_xyz_m"]
            trace.append({"frame": frame, "time_s": index / 20,
                          "position_m": position,
                          "position": dict(zip(("x", "y", "z"), position)),
                          "heading_deg": row["ego_heading_deg"],
                          "speed_mps": row["ego_speed_mps"],
                          "speed_mph": row["ego_speed_mps"] / .44704})
        (stage / "video_frames.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in mapping))
        (stage / "trace.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in trace))
        history = {"source_kind": "original_native_actor_history",
                   "assignment_id": AID, "case_id": case,
                   "reviewed_site_sha256": site["reviewed_site_sha256"],
                   "map_sha256": site["map_sha256"], "scene": site["scene"],
                   "rider_ids": site["scene"]["rider_ids"],
                   "native_actor_ids": rows[0]["native_actor_ids"],
                   "samples": rows}
        put(stage / "rider-history.json", history)
        try:
            put(stage / "rider-measurement.json", measure_original(rows, site["scene"], adapter.case))
        except ValueError as error:
            put(stage / "rider-measurement.json", {"measured": False,
                "physical_gap": str(error), "legal_abreast_judgment": None})
        videos = {}
        for name, folder in folders.items():
            video = stage / (name + ".mkv")
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-framerate", "20",
                            "-i", str(folder / "%04d.png"), "-frames:v", "900",
                            "-c:v", "ffv1", str(video)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            videos[name] = {"path": video.name, "sha256": sha(video),
                            "frame_count": 900}
            shutil.rmtree(folder)
        put(stage / "original-source-receipt.json", {
            "source_kind": "original_native_capture", "diagnostic_fixture": False,
            "case_id": case, "fps": 20, "frame_count": 900,
            "reviewed_site_sha256": site["reviewed_site_sha256"],
            "history_sha256": sha(stage / "rider-history.json"),
            "trace_sha256": sha(stage / "trace.jsonl"),
            "frame_map_sha256": sha(stage / "video_frames.jsonl"),
            "measurement_sha256": sha(stage / "rider-measurement.json"),
            "cameras": videos, "physical_acceptance": False, "legal_verdict": None})
        os.replace(stage, destination)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        adapter.cleanup()
