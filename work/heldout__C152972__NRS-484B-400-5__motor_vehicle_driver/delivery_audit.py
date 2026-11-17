"""Independent CPU delivery check for original one-way left-turn curb sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from math import hypot, isfinite
from pathlib import Path
import subprocess

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = {"oneway_geometry_original.json", "body_ground_original.json", "trace.jsonl", "video_frames.jsonl"}
SOURCES |= {name + ".mkv" for name in CAMERAS}
SOURCES |= {name + "-frames.jsonl" for name in CAMERAS}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def decoded_frame_count(path):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    require(probe.returncode == 0, "Original camera frame probe failed: " + path.name)
    streams = json.loads(probe.stdout).get("streams", [])
    require(len(streams) == 1 and str(streams[0].get("nb_read_frames", "")).isdigit(),
            "Original camera frame count absent: " + path.name)
    return int(streams[0]["nb_read_frames"])


def nearest(corners, line):
    require(isinstance(line, list) and len(line) == 2, "Original left-curb line missing")
    a, z = line
    dx, dy = z[0] - a[0], z[1] - a[1]
    length = hypot(dx, dy)
    require(length >= 1 and all(isfinite(v) for point in line for v in point), "Invalid original left-curb line")
    return min(abs(dx * (y - a[1]) - dy * (x - a[0])) / length for x, y in corners)


def audit(case_id, attempt, processed, manifest):
    root = Path(attempt).resolve()
    package = Path(manifest).resolve().parent
    entries = [row for row in read(manifest)["cases"] if row["case_id"] == case_id]
    require(len(entries) == 1, "Exact selected curb case missing")
    entry = entries[0]
    receipt = read(root / "curb_source_receipt.json")
    require(receipt.get("case_id") == case_id, "Original curb source case differs")
    hashes = receipt.get("source_sha256")
    require(isinstance(hashes, dict) and set(hashes) == SOURCES, "Original curb source inventory incomplete")
    for name, expected in hashes.items():
        source = root / name
        require(source.is_file(), "Missing required source: " + name)
        require(digest(source) == expected, "Original curb source changed: " + name)
    geometry = read(root / "oneway_geometry_original.json")
    body = read(root / "body_ground_original.json")
    require((geometry.get("source_directionality"), geometry.get("destination_directionality"), geometry.get("maneuver")) == ("one_way", "one_way", "left_turn"), "One-way left-turn source differs")
    require(geometry.get("intersection_id") and geometry.get("map_source"), "Original map identity absent")
    frames = body.get("frames")
    require(isinstance(frames, list) and frames, "Original ground body frames missing")
    trace = rows(root / "trace.jsonl")
    mapping = rows(root / "video_frames.jsonl")
    camera_maps = {name: rows(root / (name + "-frames.jsonl")) for name in CAMERAS}
    require(all(len(items) == len(frames) for items in (trace, mapping, *camera_maps.values())), "Original four-camera frame count differs")
    measured = {"approach": [], "leaving_intersection": []}
    previous = None
    for index, frame in enumerate(frames):
        number, time_s = frame.get("frame"), frame.get("time_s")
        require(type(number) is int and type(time_s) in (int, float) and isfinite(time_s), "Original body frame identity absent")
        require(previous is None or (number > previous[0] and abs(time_s - previous[1] - .05) < .005), "Original body frame order or cadence differs")
        previous = (number, time_s)
        for item in (trace[index], mapping[index], *(camera_maps[name][index] for name in CAMERAS)):
            require(item.get("native_frame", item.get("frame")) == number and abs(item.get("time_s", -1) - time_s) < .005, "Original body/trace/four-camera time join differs")
        require(mapping[index].get("video_frame") == index, "Original composed frame order differs")
        corners = frame.get("ground_corners")
        require(isinstance(corners, list) and len(corners) == 4 and all(isinstance(point, list) and len(point) == 2 and all(type(v) in (int, float) and isfinite(v) for v in point) for point in corners), "Original four-corner body footprint missing")
        phase = frame.get("phase")
        if phase in measured:
            line = geometry["source_left_curb"] if phase == "approach" else geometry["destination_left_curb"]
            measured[phase].append(nearest(corners, line))
    require(all(measured.values()), "Approach or leaving-intersection phase missing")
    versions = sorted(Path(processed).glob("v*/processing.json"))
    require(len(versions) == 1, "One saved-processing receipt required")
    saved = read(versions[0])
    require(saved.get("case_id") == case_id and saved.get("passed") is True and saved.get("missing_evidence") is False, "Saved processing did not pass exact case")
    require(saved.get("originals_preserved") is True and saved.get("timestamp_joins", {}).get("passed") is True, "Saved originals or timestamp joins failed")
    require(saved.get("native_revision", {}).get("construction_sha256") == digest(package / entry["construction"]), "Saved construction changed")
    require(all(saved.get("original_source_hashes", {}).get(name) == expected for name, expected in hashes.items()), "Saved original source differs")
    require(saved.get("final_video_checks", {}).get("passed") is True, "Saved final video decode failed")
    for name in CAMERAS:
        video = root / (name + ".mkv")
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        require(decoded.returncode == 0, "Original camera decode failed: " + name)
        require(decoded_frame_count(video) == len(frames), "Original camera video/frame-map count differs: " + name)
    require(saved.get("physical_acceptance_claimed") is False and saved.get("legal_acceptance_claimed") is False, "Diagnostic claims physical or legal acceptance")
    return {"format": "worker-oneway-curb-delivery-audit", "case_id": case_id,
            "source_sha256": hashes, "frames": len(frames), "four_original_cameras_decoded": True,
            "four_original_camera_frame_counts": {name: len(frames) for name in CAMERAS},
            "approach_left_curb_nearest_m": min(measured["approach"]),
            "departure_left_curb_nearest_m": min(measured["leaving_intersection"]),
            "saved_processing_sha256": digest(versions[0]),
            "diagnostic_fixture": True, "actual_native_capture": False,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    for name in ("case", "attempt", "processed", "manifest", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = audit(args.case, args.attempt, args.processed, args.manifest)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
