"""Source-driven CPU outcomes for a synthetic Native-shaped lane protocol.

These fixtures exercise preparation logic only. They are not CARLA captures or
evidence that any roadway or exception was physically realized.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from lane_finalizer import analyze


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def put(path, values):
    Path(path).write_text("".join(json.dumps(value, allow_nan=False) + "\n" for value in values))


def _position(row):
    pos = row["position"]
    return float(pos["x"]), float(pos["y"])


def _advance_source(attempt, kind):
    """Add consistent synthetic longitudinal travel to the static adapter fixture."""
    trace_path = attempt / "trace.jsonl"
    lane_path = attempt / "marked_lane_sources.jsonl"
    trace, lane = rows(trace_path), rows(lane_path)
    initial_inside = [list(corner) for corner in lane[0]["ego_corners_xy_m"]]
    for index, (motion, sample) in enumerate(zip(trace, lane)):
        shift = float(index)
        motion["position"]["x"] += shift
        if "position_m" in motion:
            motion["position_m"][0] += shift
        for corner in sample["ego_corners_xy_m"]:
            corner[0] += shift
        for corner in sample["lane"]["polygon_xy_m"]:
            corner[0] += shift
        if sample.get("overtaken_corners_xy_m"):
            for corner in sample["overtaken_corners_xy_m"]:
                corner[0] += shift
        if kind == "incomplete_motion":
            suffix = json.loads((attempt / "config.json").read_text())["selected_case_id"].rsplit("__", 1)[-1]
            if suffix == "within_marked_lane":
                for corner in sample["ego_corners_xy_m"]:
                    corner[1] += sample["lane"]["lane_width_m"] * 2
            else:
                sample["ego_corners_xy_m"] = [[corner[0] + shift, corner[1]]
                                                 for corner in initial_inside]
    put(trace_path, trace)
    put(lane_path, lane)


def run(case_id, kind):
    manifest = HERE / "execution-manifest.json"
    entry = next((item for item in json.loads(manifest.read_text())["cases"]
                  if item["case_id"] == case_id), None)
    if entry is None or kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown exact lane case or fixture kind")
    with TemporaryDirectory(prefix="lane-motion-", dir=ROOT / ".runtime-work") as temp:
        base = Path(temp)
        make_fixture(ROOT, ROOT / entry["fixture_recipe"], base / "fixture")
        make_attempt(manifest, case_id, base / "attempt")
        copy_sources(base / "fixture", base / "attempt")
        attempt = base / "attempt"
        _advance_source(attempt, kind)
        source = attempt / "marked_lane_sources.jsonl"
        if kind == "missing_evidence":
            source.unlink()
        names = ("video_frames.jsonl", "trace.jsonl", "marked_lane_sources.jsonl")
        sources = {name: sha256((attempt / name).read_bytes()).hexdigest()
                   for name in names if (attempt / name).is_file()}
        measured = None
        if kind == "missing_evidence":
            try:
                analyze(attempt, write_channel=False)
            except ValueError as error:
                if "Missing required source: marked_lane_sources.jsonl" not in str(error):
                    raise
            else:
                raise ValueError("Missing lane source was accepted")
            status = "unverified"
        else:
            measured = analyze(attempt, write_channel=False)["measurements"]["lane_boundary_observation"]["value"]
            trace = rows(attempt / "trace.jsonl")
            first, last = _position(trace[0]), _position(trace[-1])
            progress_m = hypot(last[0] - first[0], last[1] - first[1])
            suffix = case_id.rsplit("__", 1)[-1]
            frames = measured["frames"]
            if suffix == "within_marked_lane":
                behavior = all(frame["full_footprint_inside"] for frame in frames)
            elif suffix == "unexcused_boundary_crossing":
                behavior = any(frame["boundary_crossing"] for frame in frames)
            else:
                behavior = (any(frame["boundary_crossing"] for frame in frames)
                            and measured["measured_order_reversal"])
            status = "met" if progress_m > .25 and behavior else "not_met"
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError(f"Physical fixture {kind} yielded {status}, expected {expected}")
        return {"case_id": case_id, "fixture_kind": kind, "fixture_only": True,
                "diagnostic_fixture": True, "actual_native_capture": False,
                "physical_checks": {"maneuver": {
                    "status": status,
                    "method": "source-joined lane footprint and synthetic travel, with case-specific event check",
                    "sources": sources,
                    "missing_evidence": ["marked_lane_sources.jsonl"] if kind == "missing_evidence" else []}},
                "maneuver_completed": status == "met",
                "realized_observables": ({"original_frame_count": len(measured["frames"]),
                                          "minimum_clearance_m": min(frame["minimum_corner_clearance_m"]
                                                                     for frame in measured["frames"])}
                                         if measured is not None else {}),
                "provenance_kind": "native",
                "provenance_note": "Native-shaped source protocol test; synthetic diagnostic fixture, not Native acquisition",
                "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(args.case, args.kind, result["physical_checks"]["maneuver"]["status"],
          "synthetic_fixture_only")
