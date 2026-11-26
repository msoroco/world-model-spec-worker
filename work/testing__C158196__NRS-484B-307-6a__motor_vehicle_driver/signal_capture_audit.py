"""Independent original signal capture source and full-video decode audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def decode(video, *, probe=None, decoder=None):
    if probe is None:
        probe = lambda command: subprocess.run(command, check=True, text=True,
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if decoder is None:
        decoder = lambda command: subprocess.run(command, check=True,
                                                  stdout=subprocess.DEVNULL,
                                                  stderr=subprocess.PIPE)
    result = probe(["ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-count_frames", "-show_entries", "stream=nb_read_frames,r_frame_rate",
                    "-of", "json", str(video)])
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    need(len(streams) == 1 and streams[0].get("r_frame_rate") == "20/1" and
         int(streams[0].get("nb_read_frames", 0)) == 900,
         "original camera has wrong frame count or rate")
    decoder(["ffmpeg", "-v", "error", "-nostdin", "-i", str(video),
             "-f", "null", "-"])


def audit(attempt, case, *, probe=None, decoder=None):
    attempt = Path(attempt).resolve()
    receipt_path = attempt / "original-source-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    need(receipt.get("source_kind") == "original_native_capture" and
         receipt.get("diagnostic_fixture") is False and receipt.get("case") == case,
         "original Native source receipt mismatch")
    need(receipt.get("fps") == 20 and receipt.get("frame_count") == 900,
         "original 20 Hz duration missing")
    packet_path = attempt / "original-signal-packet.json"
    trace_path = attempt / "trace.jsonl"
    frame_map_path = attempt / "video_frames.jsonl"
    for path, key in ((packet_path, "signal_packet_sha256"),
                      (trace_path, "trace_sha256"),
                      (frame_map_path, "frame_map_sha256")):
        need(path.is_file() and sha(path) == receipt.get(key),
             "original source hash mismatch: " + path.name)
    packet = json.loads(packet_path.read_text())
    trace = rows(trace_path)
    mapping = rows(frame_map_path)
    geometry = attempt / "native-ego-geometry.jsonl"
    need(len(trace) == len(mapping) == len(packet.get("frames", [])) == 900 and
         geometry.is_file(), "original frame or body history incomplete")
    geometry_rows = rows(geometry)
    need(len(geometry_rows) == 900, "original body geometry incomplete")
    geometry_sha = sha(geometry)
    native_previous = None
    for index, (row, mapped, body) in enumerate(zip(trace, mapping, geometry_rows)):
        packet_row = packet["frames"][index]
        need(packet_row.get("frame") == index and
             packet_row.get("source_frame") == index and mapped.get("video_frame") == index and
             row.get("frame") == packet_row.get("native_frame") ==
             mapped.get("native_frame") == mapped.get("carla_frame") and
             row.get("time_s") == packet_row.get("native_time_s") == mapped.get("time_s") and
             body.get("frame") == index and
             body.get("native_frame") == row.get("frame") and
             len(body.get("ego_vertices", [])) == 8,
             "original signal/body/video frame join differs")
        ref = packet_row.get("ego_geometry_source", {})
        need(ref.get("path") == geometry.name and ref.get("sha256") == geometry_sha,
             "original body geometry source hash differs")
        if native_previous is not None:
            need(row["frame"] == native_previous[0] + 1 and
                 abs(row["time_s"] - native_previous[1] - .05) <= .002,
                 "original Native frame/time cadence differs")
        native_previous = row["frame"], row["time_s"]
    camera_refs = receipt.get("cameras")
    need(isinstance(camera_refs, dict) and set(camera_refs) == set(CAMERAS),
         "four original videos missing")
    for name in CAMERAS:
        ref = camera_refs[name]
        path = (attempt / ref["path"]).resolve()
        need(path.parent == attempt and path.is_file() and sha(path) == ref["sha256"] and
             ref.get("frame_count") == 900, "original camera source hash differs: " + name)
        decode(path, probe=probe, decoder=decoder)
    return {"format": "signal-original-source-audit", "case": case,
            "receipt_sha256": sha(receipt_path), "frame_count": 900,
            "full_decode": True, "source_verified": True,
            "actual_pixels_reviewed": False, "legal_verdict": None}
