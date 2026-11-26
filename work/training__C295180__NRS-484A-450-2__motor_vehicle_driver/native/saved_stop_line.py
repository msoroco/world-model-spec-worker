"""Measure the selected stop-line comparison from sealed saved source rows.

This meter reports a diagnostic observation, never a legal outcome. The
crosswalk and sight-point alternatives require separate constructions.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from road_source import inspect as inspect_road
from stop_line_request import CASES, FRAMES, RATE_HZ


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure(source_dir, case_id):
    source_dir = Path(source_dir)
    if case_id not in CASES.values():
        raise ValueError("Exact selected case differs")
    seal_path = source_dir / 'acquisition-seal.json'
    if not seal_path.is_file():
        seal_path = source_dir / 'source-seal.json'
    seal = json.loads(seal_path.read_text())
    if seal.get("format") != "c295180-saved-source-seal-v1" or seal.get("case_id") != case_id:
        raise ValueError("Saved source seal identity differs")
    required = ("native_samples.jsonl", "video_frames.jsonl", "stop_reference.json",
                "road.xodr")
    if set(seal.get("source_sha256", {})) != set(required):
        raise ValueError("Required source inventory differs")
    for name in required:
        if not (source_dir / name).is_file():
            raise ValueError("Missing required source: " + name)
        if digest(source_dir / name) != seal["source_sha256"][name]:
            raise ValueError("Saved source hash differs: " + name)
    reference = json.loads((source_dir / "stop_reference.json").read_text())
    road = inspect_road(source_dir / 'road.xodr')
    if (reference.get('authored_road_sha256') != digest(source_dir / 'road.xodr') or
            road['stop_line_world_y_m'] != -11 or
            road['intersection_near_boundary_world_y_m'] != -7):
        raise ValueError('Stop reference is not bound to the saved road source')
    if (reference.get("stop_sign_present") is not True or
            reference.get("governs_ego_lane") is not True or
            reference.get("near_crosswalk_present") is not False or
            reference.get("marked_stop_line_x_m") != 0 or
            reference.get("intersection_near_boundary_x_m", -1) <= 0 or
            reference.get("source_kind") not in
            ("authored_road_original_motion_unreviewed", "synthetic_cpu_fixture")):
        raise ValueError("Applicable sign, crosswalk, line or intersection source differs")
    native = read_rows(source_dir / "native_samples.jsonl")
    mapping = read_rows(source_dir / "video_frames.jsonl")
    if len(native) != FRAMES or len(mapping) != FRAMES:
        raise ValueError("Complete 600-frame original source window required")
    for index, (row, frame) in enumerate(zip(native, mapping)):
        if row.get("case_id") != case_id or row.get("frame") != index:
            raise ValueError("Original Native frame identity differs")
        if frame.get("video_frame") != index or frame.get("native_frame") != row.get("native_frame"):
            raise ValueError("Original video/Native frame join differs")
        if not isinstance(row.get("native_frame"), int):
            raise ValueError("Original Native frame missing")
        if index and row["native_frame"] <= native[index-1]["native_frame"]:
            raise ValueError("Original Native frame is nonmonotone")
        t = row.get("time_s")
        if (not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 or
                abs(frame.get("time_s", -1) - t) > 1e-5 or
                (index and abs(t - native[index-1]["time_s"] - 1 / RATE_HZ) > 1e-4)):
            raise ValueError("Original source time join differs")
        ego = row.get("ego", {})
        values = (ego.get("center_x_m"), ego.get("front_x_m"), ego.get("speed_mps"))
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("Original ego body or speed source missing")
        if ego["speed_mps"] < 0 or not .5 <= ego["front_x_m"] - ego["center_x_m"] <= 5:
            raise ValueError("Original ego body or speed source invalid")
        if index:
            previous = native[index-1]['ego']
            delta = abs(ego['center_x_m'] - previous['center_x_m'])
            allowance = max(ego['speed_mps'], previous['speed_mps']) / RATE_HZ + .3
            if delta > allowance or abs((ego['front_x_m'] - ego['center_x_m']) -
                                      (previous['front_x_m'] - previous['center_x_m'])) > .5:
                raise ValueError('Original ego trajectory and speed source differ')
    crossing = next((i for i, r in enumerate(native) if r["ego"]["front_x_m"] >= 0), None)
    if crossing is None:
        raise ValueError("No front-body stop-line crossing observed")
    entry = next((i for i, r in enumerate(native)
                  if r["ego"]["front_x_m"] >= reference["intersection_near_boundary_x_m"]), None)
    if entry is None or entry <= crossing:
        raise ValueError("Intersection entry after stop-line crossing not observed")
    stopped = [r["ego"]["speed_mps"] <= .1 and r["ego"]["front_x_m"] < 0
               for r in native[:crossing]]
    longest = run = 0
    for value in stopped:
        run = run + 1 if value else 0
        longest = max(longest, run)
    return {"format": "c295180-saved-stop-line-measurement-v1", "case_id": case_id,
            "source_kind": reference["source_kind"], "source_seal_sha256": digest(seal_path),
            "frames": FRAMES, "rate_hz": RATE_HZ,
            "first_front_stop_line_crossing_frame": crossing,
            "first_front_intersection_entry_frame": entry,
            "longest_pre_crossing_stopped_run_frames": longest,
            "engineering_stop_probe_frames": 20,
            "complete_stop_before_line_diagnostic": longest >= 20,
            "physical_completion_claimed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.source_dir, args.case), sort_keys=True))
