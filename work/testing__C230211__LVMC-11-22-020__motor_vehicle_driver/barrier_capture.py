"""Record one original 900-frame barrier passage and four synchronized cameras."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from barrier_route import measure
from package_spec import CAMERA_NAMES


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def capture(adapter, site, route, case, destination):
    destination = Path(destination).resolve()
    need(not destination.exists() and ".runtime-work" in destination.parts,
         "new original attempt belongs under .runtime-work")
    need(getattr(adapter, "native_attested", False) is True,
         "attested Native CARLA adapter required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="barrier-original-", dir=destination.parent))
    try:
        adapter.configure(route)
        adapter.spawn()
        frame_dirs = {name: stage / ("frames-" + name) for name in CAMERA_NAMES}
        for folder in frame_dirs.values():
            folder.mkdir()
        rows, mapping, trace = [], [], []
        previous = None
        for index in range(900):
            frame, time_s = adapter.tick()
            need(type(frame) is int and type(time_s) in (int, float),
                 "original Native frame/time missing")
            if previous is not None:
                need(frame == previous[0] + 1 and
                     abs(time_s - previous[1] - .05) <= .002,
                     "original Native 20 Hz cadence differs")
            previous = frame, time_s
            row = adapter.read(frame, time_s)
            need(row.get("frame") == frame and row.get("time_s") == time_s and
                 len(row.get("ego_footprint_vertices", [])) == 4,
                 "original body/frame readback missing")
            images = adapter.pixels(frame)
            need(set(images) == set(CAMERA_NAMES), "four original cameras required")
            hashes = {}
            for name in CAMERA_NAMES:
                image = images[name]
                raw = image.get("png")
                need(image.get("frame") == frame and isinstance(raw, bytes) and
                     raw.startswith(b"\x89PNG\r\n\x1a\n"),
                     "original camera frame or pixels missing: " + name)
                (frame_dirs[name] / f"{index:04d}.png").write_bytes(raw)
                hashes[name] = hashlib.sha256(raw).hexdigest()
            rows.append(row)
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "native_frame": frame, "time_s": time_s,
                            "camera_png_sha256": hashes})
            trace.append({"frame": frame, "time_s": time_s,
                          "position_m": row["ego_position_m"],
                          "position": {"x": row["ego_position_m"][0],
                                       "y": row["ego_position_m"][1],
                                       "z": row["ego_position_m"][2]},
                          "heading_deg": row["heading_deg"],
                          "speed_mps": row["speed_mps"],
                          "speed_mph": row["speed_mps"] / .44704})
        (stage / "video_frames.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in mapping))
        (stage / "trace.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in trace))
        packet = {key: site[key] for key in ("assignment_id", "map_id", "highway_id",
                   "city_highway_status", "barrier_id", "barrier_rectangle",
                   "barrier_geometry_source", "road_y_bounds",
                   "surrounding_conditions_source")}
        packet.update({"case_id": case,
                       "route_candidate": "wide" if case.endswith("__wide_clearance") else "near",
                       "original_trace_id": hashlib.sha256((case + str(rows[0]["frame"])).encode()).hexdigest(),
                       "ego_actor_id": rows[0]["ego_actor_id"],
                       "driver_actor_id": site["driver_actor_id"],
                       "barrier_actor_id": rows[0]["barrier_actor_id"],
                       "reviewed_site_sha256": site["reviewed_site_sha256"],
                       "route_source_sha256": route["source"]["sha256"],
                       "frames": rows})
        write(stage / "barrier-packet.json", packet)
        write(stage / "barrier-measurement.json", measure(stage / "barrier-packet.json"))
        videos = {}
        for name, folder in frame_dirs.items():
            video = stage / (name + ".mkv")
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-framerate", "20",
                            "-i", str(folder / "%04d.png"), "-frames:v", "900",
                            "-c:v", "ffv1", str(video)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            videos[name] = {"path": video.name, "sha256": sha(video),
                            "frame_count": 900}
            shutil.rmtree(folder)
        write(stage / "original-source-receipt.json", {
            "source_kind": "original_native_capture", "diagnostic_fixture": False,
            "case_id": case, "fps": 20, "frame_count": 900,
            "reviewed_site_sha256": site["reviewed_site_sha256"],
            "packet_sha256": sha(stage / "barrier-packet.json"),
            "trace_sha256": sha(stage / "trace.jsonl"),
            "frame_map_sha256": sha(stage / "video_frames.jsonl"),
            "measurement_sha256": sha(stage / "barrier-measurement.json"),
            "cameras": videos, "physical_acceptance": False,
            "legal_verdict": None})
        os.replace(stage, destination)
        return destination
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        adapter.cleanup()
