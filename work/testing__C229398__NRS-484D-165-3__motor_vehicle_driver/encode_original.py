"""Losslessly encode only the original source images after Native capture."""

from __future__ import annotations

import hashlib
import json
import subprocess
import argparse
from pathlib import Path

from parked_lamps import audit_saved_capture, require

VIEWS = {"front": "overview", "rear": "approach",
         "left": "reference_corner", "right": "driver_reference"}


def audit_encoded_views(attempt, expected_frames, *, ffmpeg="ffmpeg", ffprobe="ffprobe"):
    """Independently verify sealed four-view bytes and decode every video frame.

    The receipt is a software media audit. It cannot establish that the lamps
    are visible or that a scene meets a legal standard.
    """
    root = Path(attempt)
    index_path = root / "encoded-views.json"
    require(index_path.is_file(), "encoded view index missing")
    index = json.loads(index_path.read_text())
    views = index.get("views")
    require(isinstance(views, dict) and set(views) == set(VIEWS.values()),
            "exact four encoded views required")
    audited = {}
    for camera, view in VIEWS.items():
        item = views[view]
        require(item.get("source_camera") == camera and item.get("path") == view + ".mkv" and
                item.get("source") == "original_png_index" and item.get("codec") == "ffv1" and
                item.get("fps") == 20 and item.get("frames") == expected_frames,
                view + " source/cadence identity mismatch")
        target = root / item["path"]
        require(target.is_file() and target.resolve().is_relative_to(root.resolve()) and
                file_sha(target) == item.get("sha256"), view + " encoded bytes changed")
        probe = subprocess.run([ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=nb_read_frames,r_frame_rate,codec_name",
                                "-of", "json", str(target)], capture_output=True, text=True,
                               timeout=120, check=True)
        streams = json.loads(probe.stdout).get("streams", [])
        require(len(streams) == 1 and streams[0].get("nb_read_frames") == str(expected_frames) and
                streams[0].get("r_frame_rate") == "20/1" and streams[0].get("codec_name") == "ffv1",
                view + " encoded frame count, rate or codec mismatch")
        decoded = subprocess.run([ffmpeg, "-v", "error", "-xerror", "-i", str(target),
                                  "-map", "0:v:0", "-f", "null", "-"],
                                 capture_output=True, text=True, timeout=900)
        require(decoded.returncode == 0, view + " full decode failed: " + decoded.stderr[-500:])
        audited[view] = {"path": item["path"], "sha256": item["sha256"],
                         "frames_decoded": expected_frames, "source_camera": camera,
                         "codec": "ffv1", "fps": 20}
    return {"format": "c229398-independent-four-view-decode-v1", "case_id": index.get("case_id"),
            "encoded_index_sha256": file_sha(index_path), "views": audited,
            "physical_visibility_status": "unreviewed", "legal_verdict": None}


def audit_encoded(attempt, case_key, map_sha256, *, ffmpeg="ffmpeg", ffprobe="ffprobe"):
    root = Path(attempt)
    capture = root / "capture"
    audit_saved_capture(capture, case_key, map_sha256)
    packet_path = capture / "capture-packet.json"
    index = json.loads((root / "encoded-views.json").read_text())
    require(index.get("case_id") == json.loads(packet_path.read_text()).get("case_id") and
            index.get("capture_packet_sha256") == file_sha(packet_path),
            "encoded views differ from original capture packet")
    return audit_encoded_views(root, 900, ffmpeg=ffmpeg, ffprobe=ffprobe)


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
                      "position": {"x": position[0], "y": position[1], "z": position[2]},
                      "heading_deg": row["heading_deg"],
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
    observations = [json.loads(line) for line in history_path.read_text().splitlines()]
    (root / "parked_lamp_observations.jsonl").write_text("".join(
        json.dumps({"time_s": row["time_s"], "value": row}, sort_keys=True) + "\n"
        for row in observations))
    (root / "site_context.json").write_text(json.dumps({
        "reviewed_site_packet": json.loads((capture / "site_packet.json").read_text()),
        "site_packet_sha256": file_sha(capture / "site_packet.json")
    }, sort_keys=True) + "\n")
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


def main():
    parser = argparse.ArgumentParser(description="Audit a saved original parked-lamp capture and four encoded views")
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case-key", required=True)
    parser.add_argument("--map-sha256", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    result = audit_encoded(args.attempt, args.case_key, args.map_sha256)
    target = Path(args.receipt)
    with target.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
