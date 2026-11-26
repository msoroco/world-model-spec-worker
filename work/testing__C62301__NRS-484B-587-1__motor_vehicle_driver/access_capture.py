"""Capture 900 source-sealed Native controlled-access frames and four lossless views."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from package_spec import AID, CAMERA_NAMES
from access_probe import measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n")


def capture(adapter, site, case, destination):
    destination = Path(destination).resolve()
    if destination.exists() or ".runtime-work" not in destination.parts or getattr(adapter, "native_attested", False) is not True:
        raise ValueError("attested original Native attempt belongs under fresh .runtime-work path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="access-original-", dir=destination.parent))
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
                raise ValueError("original Native vehicle and lane readback absent")
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
            row["boundary_xy"] = row["position_xyz_m"][:2]
            row["native_frame"] = native_frame
            row["frame"] = index
            rows.append(row)
            mapping.append({"video_frame": index, "native_frame": native_frame,
                            "carla_frame": native_frame, "time_s": time_s,
                            "camera_png_sha256": hashes})
            position = row["position_xyz_m"]
            trace.append({"frame": native_frame, "time_s": time_s,
                          "position_m": position,
                          "position": dict(zip(("x", "y", "z"), position)),
                          "heading_deg": row["heading_deg"],
                          "speed_mps": row["speed_mps"],
                          "speed_mph": row["speed_mps"] / .44704})
        (stage / "video_frames.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in mapping))
        (stage / "trace.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in trace))
        history = {"source_kind": "original_native_actor_history", "assignment_id": AID,
                   "case_id": case, "reviewed_site_sha256": site["reviewed_site_sha256"],
                   "map_sha256": site["map_sha256"], "driver_actor_id": site["driver_actor_id"],
                   "ego_actor_id": rows[0]["actor_ids"][0], "actor_ids": rows[0]["actor_ids"],
                   "authority_source": site["authority_source"],
                   "highway_source": site["highway_source"],
                   "boundary_source": site["boundary_source"],
                   "official_notice_source": site["official_notice_source"],
                   "public_highway": site["public_highway"],
                   "controlled_access_determination": site["controlled_access_determination"],
                   "authority_designated_devices": site["authority_designated_devices"],
                   "boundary_x_m": site["boundary_x_m"],
                   "indicated_points": site["indicated_points"],
                   "target_point": site["target_point"], "requested_direction": site["requested_direction"],
                   "samples": rows}
        put(stage / "access-history.json", history)
        probe_site = {key: history[key] for key in ("authority_source", "highway_source",
                      "boundary_source", "controlled_access_determination", "boundary_x_m",
                      "indicated_points", "official_notice_source")}
        probe_site["vehicle_id"] = history["driver_actor_id"]
        frames = [{"original_frame": row["native_frame"], "time_s": row["time_s"],
                   "vehicle_id": row["driver_id"], "xy": row["boundary_xy"],
                   "source_ref": row["source_ref"]} for row in rows]
        try:
            measured = measure(probe_site, frames)
        except ValueError as error:
            measured = {"measured": False, "physical_gap": str(error),
                        "legal_interpretation": "unresolved"}
        put(stage / "access-measurement.json", measured)
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
            "history_sha256": sha(stage / "access-history.json"),
            "trace_sha256": sha(stage / "trace.jsonl"),
            "frame_map_sha256": sha(stage / "video_frames.jsonl"),
            "measurement_sha256": sha(stage / "access-measurement.json"),
            "cameras": videos, "physical_acceptance": False, "legal_verdict": None})
        os.replace(stage, destination)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        adapter.cleanup()
