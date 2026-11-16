"""Independent saved-source audit for the first heavy marked-lane CPU fixture.

This audits source integrity and measured geometry. It never decides a lawful
lane boundary, either exception, or physical camera visibility.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHANNELS = ("native_lane_boundaries", "heavy_vehicle_footprint",
            "lane_boundary_overlap", "passing_context",
            "turn_preparation_context", "four_camera_originals")


def _file(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Missing original delivery source: " + name)
    return path


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _decode(path: Path, frames: int) -> dict:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames",
         "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    if int(probe.stdout.strip()) != frames:
        raise ValueError("Original camera decoded frame count differs: " + path.name)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    return {"sha256": _sha(path), "decoded_frames": frames}


def _clearance(observation: dict) -> float:
    lane = observation["lane"]
    cx, cy = lane["center_xy_m"]
    fx, fy = lane["heading_xy"]
    if abs(fx * fx + fy * fy - 1) > 1e-6 or lane["width_m"] <= 0:
        raise ValueError("Original delivery lane geometry invalid")
    values = []
    for component in observation["heavy_vehicle_components"]:
        corners = component["corners_xy_m"]
        if len(corners) != 4:
            raise ValueError("Original delivery body corners incomplete")
        lateral = [(x - cx) * -fy + (y - cy) * fx for x, y in corners]
        values.extend((lane["width_m"] / 2 - max(lateral),
                       lane["width_m"] / 2 + min(lateral)))
    if not values:
        raise ValueError("Original delivery heavy body absent")
    return min(values)


def audit(root: Path, case_id: str, *, negative_camera: bool = False) -> dict:
    root = Path(root)
    report = json.loads(_file(root, "analysis-report.json").read_text())
    result = json.loads(_file(root, "result.json").read_text())
    if report.get("case_id") != case_id or result.get("case_id") != case_id:
        raise ValueError("Saved delivery case identity differs")
    measurement = report["measurements"]["heavy_lane_footprint"]
    sources = measurement["sources"]
    required = {"native_three_lane_survey.json", "heavy_lane_sources.jsonl",
                "trace.jsonl", "video_frames.jsonl", *(name + ".mkv" for name in CAMERAS)}
    if set(sources) != required:
        raise ValueError("Saved delivery source inventory differs")
    for name, digest in sources.items():
        actual = name + ".missing" if negative_camera and name == "overview.mkv" else name
        if _sha(_file(root, actual)) != digest:
            raise ValueError("Original delivery source hash differs: " + name)
    survey = json.loads(_file(root, "native_three_lane_survey.json").read_text())
    lanes = {(lane["road_id"], lane["lane_id"]) for lane in survey["lanes"]}
    if len(lanes) != 3:
        raise ValueError("Original delivery three-lane survey differs")
    body = _rows(_file(root, "heavy_lane_sources.jsonl"))
    trace = _rows(_file(root, "trace.jsonl"))
    frame_map = _rows(_file(root, "video_frames.jsonl"))
    samples = measurement["value"]["frames"]
    if not body or len(body) != len(trace) or len(body) != len(frame_map) or len(body) != len(samples):
        raise ValueError("Original delivery frame count differs")
    clearances = []
    for index, (observation, motion, frame, sample) in enumerate(zip(body, trace, frame_map, samples)):
        identity = (observation["frame"], observation["time_s"])
        if (identity != (motion["frame"], motion["time_s"]) or
                identity != (frame["carla_frame"], frame["time_s"]) or
                frame["video_frame"] != index or
                (observation["lane"]["road_id"], observation["lane"]["lane_id"]) not in lanes or
                observation["survey_sha256"] != sources["native_three_lane_survey.json"]):
            raise ValueError("Original delivery body/trace/video join differs")
        value = _clearance(observation)
        if sample["frame"] != identity[0] or sample["time_s"] != identity[1] or sample["minimum_clearance_m"] != value:
            raise ValueError("Saved delivery lane clearance differs from originals")
        clearances.append(value)
    if measurement["value"]["minimum_clearance_m"] != min(clearances):
        raise ValueError("Saved delivery minimum clearance differs")
    evidence = {item["name"]: item for item in result["recording_evidence"]}
    if set(evidence) != set(CHANNELS):
        raise ValueError("Saved delivery recording channel inventory differs")
    for name, item in evidence.items():
        channel = _file(root, item["reference"])
        if _sha(channel) != item["sha256"] or len(_rows(channel)) != len(body):
            raise ValueError("Saved delivery derived channel differs: " + name)
    decoded = {name: _decode(_file(root, name + ".mkv"), len(body)) for name in CAMERAS}
    return {"format": "worker-heavy-lane-delivery-audit-fixture", "case_id": case_id,
            "fixture_only": True, "frames": len(body), "source_join_verified": True,
            "minimum_clearance_m": min(clearances), "four_camera_decode": decoded,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative-camera", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(Path(args.attempt), args.case,
                           negative_camera=args.negative_camera), indent=2))


if __name__ == "__main__":
    main()
