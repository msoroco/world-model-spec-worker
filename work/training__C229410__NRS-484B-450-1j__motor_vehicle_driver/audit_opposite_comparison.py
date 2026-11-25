"""Independent raw-source comparison for the opposite-side 75-foot sweep."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_FILES = ("road.xodr", "video_frames.jsonl", "entrance-context.json",
                "acquisition-provenance.json")
AUTHORITY_FACTS = ("station_identity", "driveway_entrance", "highway_boundary",
                   "activity_and_directions")
LIMIT_M = 22.86


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stream(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def decoded_frames(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of",
                            "default=noprint_wrappers=1:nokey=1", str(path)],
                           capture_output=True, text=True, timeout=120)
    if probe.returncode or probe.stdout.strip() != "600":
        raise ValueError("Original camera full decode differs: " + path.name)


def observe(folder):
    folder = Path(folder)
    context = json.loads((folder / "entrance-context.json").read_text())
    if context.get("source_kind") not in ("synthetic_diagnostic", "original_native"):
        raise ValueError("Unidentified entrance source")
    entrance = context.get("entrance") or {}
    if entrance.get("road_side") != "south":
        raise ValueError("Fixed entrance side differs")
    if context.get("initial_activity") != "parked" or context.get("exception_context") != "none":
        raise ValueError("Fixed activity or exception differs")
    if context["source_kind"] == "original_native":
        authority = folder / "authority/manifest.json"
        if not authority.is_file() or digest(authority) != context.get("authority_manifest_sha256"):
            raise ValueError("Original authority manifest missing or changed")
        facts = context.get("authority_source_sha256") or {}
        for name in AUTHORITY_FACTS:
            source = folder / "authority" / (name + ".source")
            if not source.is_file() or digest(source) != facts.get(name):
                raise ValueError("Original authority fact missing or changed: " + name)
    motion = stream(folder / "native-vehicle.jsonl")
    frames = stream(folder / "video_frames.jsonl")
    if len(motion) != 600 or len(frames) != 600:
        raise ValueError("Original motion or frame map incomplete")
    stationary = []
    for index, (row, frame) in enumerate(zip(motion, frames)):
        native = row.get("native_frame")
        if (type(native) is not int or frame.get("native_frame") != native
                or row.get("video_frame") != index or frame.get("video_frame") != index
                or row.get("time_s") != index / 20 or frame.get("time_s") != index / 20
                or frame.get("camera_native_frames") != {name: native for name in CAMERAS}):
            raise ValueError("Original frame, time or four-camera join differs")
        if row.get("source_kind") != context["source_kind"]:
            raise ValueError("Original motion provenance differs")
        points = row.get("body_xy_m")
        if not isinstance(points, list) or len(points) < 4:
            raise ValueError("Full vehicle body missing")
        if any(not isinstance(point, list) or len(point) != 2
               or any(type(value) not in (int, float) or not math.isfinite(value)
                      for value in point) for point in points):
            raise ValueError("Invalid original body corner")
        speed = row.get("speed_mps")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("Invalid original speed")
        if speed <= .1 and index >= 300:
            if row.get("center_xy_m", [None, None])[1] <= 0:
                raise ValueError("Rest is not on the opposite side")
            xs = [point[0] for point in points]
            gap = max(0, entrance["x_min_m"] - max(xs),
                      min(xs) - entrance["x_max_m"])
            stationary.append(gap)
    if len(stationary) < 100 or any(row["speed_mps"] > .1 for row in motion[-100:]):
        raise ValueError("Sustained opposite-side rest missing")
    for name in CAMERAS:
        video = folder / (name + ".mkv")
        if not video.is_file():
            raise ValueError("Missing original camera: " + name)
        if context["source_kind"] == "original_native":
            decoded_frames(video)
    return {"motion": motion, "minimum_gap_m": min(stationary),
            "motion_sha256": digest(folder / "native-vehicle.jsonl"),
            "context": context, "source_kind": context["source_kind"]}


def compare(far, near):
    far, near = Path(far), Path(near)
    for name in SOURCE_FILES:
        if digest(far / name) != digest(near / name):
            raise ValueError("Fixed road, timing or source context differs: " + name)
    a, b = observe(far), observe(near)
    if a["source_kind"] != b["source_kind"]:
        raise ValueError("Paired provenance differs")
    for index, (left, right) in enumerate(zip(a["motion"], b["motion"])):
        for key in ("native_frame", "video_frame", "time_s", "actor_id", "blueprint_id"):
            if left.get(key) != right.get(key):
                raise ValueError("Fixed actor or timing differs at frame " + str(index))
    if not a["minimum_gap_m"] > LIMIT_M > b["minimum_gap_m"]:
        raise ValueError("Opposite-side raw gap does not bracket 75 feet")
    return {"format": "c229410-opposite-source-comparison-v1", "passed": True,
            "source_kind": a["source_kind"], "far_motion_sha256": a["motion_sha256"],
            "near_motion_sha256": b["motion_sha256"],
            "fixed_source_sha256": {name: digest(far / name) for name in SOURCE_FILES},
            "far_raw_body_edge_gap_m": a["minimum_gap_m"],
            "near_raw_body_edge_gap_m": b["minimum_gap_m"],
            "statutory_reference_method_adopted": False,
            "physical_or_legal_result_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--far", required=True)
    parser.add_argument("--near", required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.far, args.near), sort_keys=True))
