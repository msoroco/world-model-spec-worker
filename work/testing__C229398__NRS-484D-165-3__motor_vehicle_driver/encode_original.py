"""Losslessly encode only the original source images after Native capture."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from parked_lamps import audit_saved_capture, require

VIEWS = {"front": "overview", "rear": "approach",
         "left": "reference_corner", "right": "driver_reference"}


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def original_rows(capture):
    capture = Path(capture)
    history = [json.loads(line) for line in (capture / "original_history.jsonl").read_text().splitlines()]
    mapping = json.loads((capture / "original_frame_map.json").read_text())["frames"]
    require(len(history) == len(mapping) == 900, "original history/frame map count mismatch")
    frames, trace = [], []
    for tick, (row, view) in enumerate(zip(history, mapping)):
        native = row.get("native_frame")
        require(row.get("frame_index") == tick and view.get("frame_index") == tick and
                type(native) is int and view.get("native_frame") == native,
                "original frame identity join failed")
        require(abs(row.get("time_s", -1) - tick / 20) <= .003,
                "original 20 Hz time join failed")
        position = row.get("position_m")
        require(isinstance(position, list) and len(position) == 3 and
                all(type(v) in (int, float) for v in position), "original vehicle position missing")
        frames.append({"video_frame": tick, "carla_frame": native, "native_frame": native,
                       "time_s": row["time_s"]})
        trace.append({"frame": native, "time_s": row["time_s"],
                      "position_m": position, "speed_mps": row["speed_mps"],
                      "light_state_bits": row["native_lamp_state_bits"],
                      "parking_brake": row["parking_brake"]})
    return frames, trace


def encode(attempt, case_key, map_sha256, *, ffmpeg="ffmpeg", ffprobe="ffprobe"):
    root = Path(attempt)
    capture = root / "capture"
    packet_path = capture / "capture-packet.json"
    packet = json.loads(packet_path.read_text())
    audit_saved_capture(capture, case_key, map_sha256)
    require(packet.get("camera_image_format") == "original_png" and packet.get("frame_count") == 900,
            "900 original PNG frames required for encoding")
    history_path = capture / packet.get("original_history_path", "")
    require(history_path.is_file() and history_path.resolve().is_relative_to(capture.resolve()) and
            file_sha(history_path) == packet.get("original_history_sha256"),
            "sealed original history missing or changed")
    frames, trace = original_rows(capture)
    for name, values in (("video_frames.jsonl", frames), ("trace.jsonl", trace)):
        target = root / name
        require(not target.exists(), "retain prior original " + name)
        target.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in values))
    results = {}
    for camera, view in VIEWS.items():
        target = root / (view + ".mkv")
        require(not target.exists(), "retain prior original encoded view")
        pattern = capture / "cameras" / camera / "%04d.png"
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-framerate", "20",
                   "-start_number", "0", "-i", str(pattern), "-frames:v", "900", "-c:v", "ffv1",
                   "-level", "3", "-pix_fmt", "bgr0", str(target)]
        subprocess.run(command, check=True, capture_output=True, timeout=900)
        probe = subprocess.run([ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=nb_read_frames,r_frame_rate", "-of", "json",
                                str(target)], check=True, capture_output=True, text=True, timeout=120)
        streams = json.loads(probe.stdout).get("streams", [])
        require(len(streams) == 1 and streams[0].get("nb_read_frames") == "900" and
                streams[0].get("r_frame_rate") == "20/1", view + " encoded frame count or cadence wrong")
        results[view] = {"source_camera": camera, "path": target.name,
                         "sha256": file_sha(target),
                         "frames": 900, "fps": 20, "codec": "ffv1", "source": "original_png_index"}
    (root / "encoded-views.json").write_text(json.dumps({"case_id": packet["case_id"],
        "capture_packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        "views": results, "physical_visibility_status": "unreviewed"}, indent=2, sort_keys=True) + "\n")
    return results
