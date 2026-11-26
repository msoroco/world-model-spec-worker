"""Record one original Native signal encounter at 20 Hz for 900 frames.

The adapter must return live signal, body, and camera observations. This module
does not infer a statutory verdict from a requested entry phase.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from construction import CAMERAS, construct
from signal_measurement import measure


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def capture(adapter, scene, case, destination):
    """Capture an original attempt; keep a failed attempt out of the destination."""
    destination = Path(destination)
    need(not destination.exists(), "original destination already exists")
    need(getattr(adapter, "native_attested", False) is True,
         "attested Native adapter required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="signal-original-", dir=destination.parent))
    owned = []
    try:
        built = construct(adapter, scene, case)
        owned.append(built["ego"])
        frame_dirs = {name: stage / ("frames-" + name) for name in CAMERAS}
        for folder in frame_dirs.values():
            folder.mkdir()
        rows = []
        frame_map = []
        previous = None
        for index in range(900):
            snapshot = adapter.tick(built)
            native_frame, native_time = snapshot.get("frame"), snapshot.get("time_s")
            need(type(native_frame) is int and type(native_time) in (int, float),
                 "Native frame/time required")
            if previous is not None:
                need(native_frame == previous[0] + 1 and
                     abs(native_time - previous[1] - .05) <= .002,
                     "original Native 20 Hz join failed")
            previous = native_frame, native_time
            observed = adapter.read_signal_row(native_frame, built, scene)
            need(observed.get("origin") == "native_world_snapshot" and
                 observed.get("native_frame") == native_frame and
                 observed.get("native_time_s") == native_time,
                 "original signal/body readback missing")
            row = dict(observed)
            row.pop("origin")
            row["frame"] = row["source_frame"] = index
            row["time_s"] = index / 20.0
            pixels = adapter.read_cameras(native_frame, built)
            need(isinstance(pixels, dict) and set(pixels) == set(CAMERAS),
                 "four original cameras required")
            hashes = {}
            for name in CAMERAS:
                image = pixels[name]
                raw = image.get("png")
                need(image.get("frame") == native_frame and
                     isinstance(raw, bytes) and raw.startswith(b"\x89PNG\r\n\x1a\n"),
                     "original camera frame or pixel bytes missing: " + name)
                (frame_dirs[name] / f"{index:04d}.png").write_bytes(raw)
                hashes[name] = hashlib.sha256(raw).hexdigest()
            rows.append(row)
            frame_map.append({"video_frame": index, "carla_frame": native_frame,
                              "native_frame": native_frame, "time_s": native_time,
                              "camera_png_sha256": hashes})
        packet = {"layout": scene["layout"], "route_id": scene["selected_route_id"],
                  "signal_id": scene["selected_signal_id"], "frames": rows}
        packet.update(adapter.source_bindings(scene))
        geometry = stage / "native-ego-geometry.jsonl"
        geometry_records = []
        for row in rows:
            vertices = row.pop("ego_vertices")
            row["position_m"] = [sum(point[axis] for point in vertices) / 8
                                 for axis in (0, 1, 2)]
            geometry_records.append({"frame": row["frame"],
                                     "native_frame": row["native_frame"],
                                     "ego_vertices": vertices,
                                     "ego_front_signed_distance_m":
                                     row["ego_front_signed_distance_m"]})
        geometry.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                    for row in geometry_records), encoding="utf-8")
        geometry_source = {"path": geometry.name, "sha256": sha(geometry)}
        for row in rows:
            row["ego_geometry_source"] = geometry_source
        trace_rows = [{"frame": row["native_frame"], "time_s": row["native_time_s"],
                       "position": {"x": row["position_m"][0],
                                    "y": row["position_m"][1],
                                    "z": row["position_m"][2]},
                       "position_m": row["position_m"],
                       "heading_deg": row["heading_deg"],
                       "speed_mps": row["speed_mps"],
                       "speed_mph": row["speed_mps"] / 0.44704}
                      for row in rows]
        (stage / "trace.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in trace_rows),
            encoding="utf-8")
        packet["native_result"] = {"path": "trace.jsonl", "sha256": sha(stage / "trace.jsonl")}
        write(stage / "original-signal-packet.json", packet)
        profile = ("yellow_non_alone" if case == "yellow_non_alone" else
                   "red_other_route" if case == "red_other_route" else
                   "steady_yellow_alone")
        measurement = measure(packet, case_profile=profile)
        write(stage / "signal-measurement.json", measurement)
        (stage / "video_frames.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_map),
            encoding="utf-8")
        videos = {}
        for name, folder in frame_dirs.items():
            path = stage / (name + ".mkv")
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-framerate", "20",
                            "-i", str(folder / "%04d.png"), "-frames:v", "900",
                            "-c:v", "ffv1", str(path)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            videos[name] = {"path": path.name, "sha256": sha(path),
                            "frame_count": 900}
            shutil.rmtree(folder)
        write(stage / "original-source-receipt.json",
              {"source_kind": "original_native_capture", "diagnostic_fixture": False,
               "case": case, "frame_count": 900, "fps": 20,
               "signal_packet_sha256": sha(stage / "original-signal-packet.json"),
               "trace_sha256": sha(stage / "trace.jsonl"),
               "frame_map_sha256": sha(stage / "video_frames.jsonl"),
               "cameras": videos, "physical_acceptance": False,
               "legal_verdict": None})
        os.replace(stage, destination)
        return measurement
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        try:
            adapter.brake()
        finally:
            try:
                for actor in reversed(owned):
                    adapter.destroy(actor)
            finally:
                adapter.restore()
