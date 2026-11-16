"""Source-shaped CPU fixture for heavy-lane physical outcome branches.

The copied saved attempt and its videos are synthetic. This tests the checker
and source joins only; it does not establish a real Native or legal outcome.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from delivery_audit import audit
from heavy_physical_outcome import CAMERAS, audit_saved


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources

PREFIX = HERE.name + "__"
DERIVED = ("analysis-report.json", "result.json", "native_lane_boundaries.jsonl",
           "heavy_vehicle_footprint.jsonl", "lane_boundary_overlap.jsonl",
           "passing_context.jsonl", "turn_preparation_context.jsonl",
           "four_camera_originals.jsonl")


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _put(path, rows):
    path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))


def _alter(attempt, suffix, kind):
    trace_path = attempt / "trace.jsonl"
    body_path = attempt / "heavy_lane_sources.jsonl"
    trace, body = _rows(trace_path), _rows(body_path)
    first_y = trace[0]["position"]["y"]
    for index, (motion, observation) in enumerate(zip(trace, body)):
        fraction = index / (len(trace) - 1)
        dx = (1.0 if suffix == "within_marked_lane" else 4.0) * fraction if kind == "complete_motion" else 0.0
        dy = 0.0
        if kind == "incomplete_motion" and suffix in (
                "unexcused_boundary_crossing", "lawful_turn_preparation_boundary_crossing"):
            dy = first_y - motion["position"]["y"]
        motion["position"]["x"] += dx
        motion["position"]["y"] += dy
        if "position_m" in motion:
            motion["position_m"][0] += dx
            motion["position_m"][1] += dy
        for component in observation["heavy_vehicle_components"]:
            for corner in component["corners_xy_m"]:
                corner[0] += dx
                corner[1] += dy
            if suffix == "passing_boundary_crossing" and kind == "complete_motion":
                component["velocity_xy_mps"][0] = 10.0
        if suffix == "passing_boundary_crossing" and kind == "complete_motion":
            other = observation["overtaken"]
            for corner in other["corners_xy_m"]:
                corner[0] -= 8.0
            motion["speed_mps"] = 10.0
        observation["lane"]["center_xy_m"][0] += dx
    _put(trace_path, trace)
    _put(body_path, body)


def run(case_id, kind, *, negative_review=False):
    if not case_id.startswith(PREFIX):
        raise ValueError("Wrong heavy-lane case identity")
    suffix = case_id[len(PREFIX):]
    manifest = HERE / "provisional-manifest.json"
    entries = [entry for entry in json.loads(manifest.read_text())["cases"]
               if entry["case_id"] == case_id]
    if len(entries) != 1 or kind not in (
            "complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown heavy-lane physical fixture")
    entry = entries[0]
    with TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="heavy-physical-") as temp:
        base = Path(temp)
        make_fixture(ROOT, ROOT / entry["fixture_recipe"], base / "fixture")
        attempt = base / "attempt"
        make_attempt(manifest, case_id, attempt)
        copy_sources(base / "fixture", attempt)
        for name in DERIVED:
            (attempt / name).unlink(missing_ok=True)
        if kind == "missing_evidence":
            (attempt / "heavy_lane_sources.jsonl").unlink()
        else:
            _alter(attempt, suffix, kind)
        command = [sys.executable, str(attempt / "heavy_lane_finalizer.py"),
                   "--attempt", str(attempt), "--output", str(attempt / "analysis-report.json")]
        env = dict(os.environ)
        env["PYTHONPATH"] = str((ROOT / "runtime/scenario_pipeline").resolve()) + os.pathsep + str(attempt)
        finished = subprocess.run(command, env=env, text=True, capture_output=True)
        if kind == "missing_evidence":
            expected = "Missing required source: heavy_lane_sources.jsonl"
            if finished.returncode == 0 or expected not in finished.stderr:
                raise ValueError("Missing source was not rejected by saved finalizer")
            result = {"case_id": case_id, "fixture_kind": kind,
                      "physical_checks": {"maneuver": {"status": "unverified",
                          "method": "saved finalizer rejects missing original heavy-body stream",
                          "sources": {"trace.jsonl": sha256((attempt / "trace.jsonl").read_bytes()).hexdigest()},
                          "missing_evidence": ["heavy_lane_sources.jsonl"]}},
                      "maneuver_completed": False, "realized_observables": {},
                      "provenance_kind": "native", "diagnostic_fixture": True,
                      "actual_native_capture": False, "physical_acceptance_claimed": False,
                      "legal_exception_decided": False}
        else:
            if finished.returncode:
                raise ValueError("Saved finalizer failed: " + finished.stderr[-1000:])
            report = json.loads((attempt / "analysis-report.json").read_text())
            joined = audit(attempt, case_id)
            pixel_review = {"case_id": case_id, "fixture_only": True,
                            "actual_native_capture": False,
                            "review_method": "frame_by_frame_originals",
                            "reviewer_id": "synthetic-cpu-fixture",
                            "reviewed_at_utc": "fixture-clock-only",
                            "cameras": {name: {"source_sha256": joined["four_camera_decode"][name]["sha256"],
                                               "reviewed_frames": joined["frames"],
                                               "frames": [{"video_frame": index,
                                                           "required_markings_visible": True,
                                                           "required_bodies_visible": True}
                                                          for index in range(joined["frames"])]}
                                        for name in CAMERAS}}
            result = audit_saved(attempt, case_id, pixel_review,
                                 allow_fixture=not negative_review)
            expected = "met" if kind == "complete_motion" else "not_met"
            if result["physical_checks"]["maneuver"]["status"] != expected:
                raise ValueError("Physical fixture yielded another branch: " +
                                 result["physical_checks"]["maneuver"]["status"])
            result.update(fixture_kind=kind, diagnostic_fixture=True,
                          actual_native_capture=False, physical_acceptance_claimed=False,
                          provenance_note="Native-shaped synthetic source protocol; pixel review is fixture input only")
        print(case_id, kind, result["physical_checks"]["maneuver"]["status"],
              "synthetic_fixture_only")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative-review", action="store_true",
                        help="Verify that the real-capture path rejects fixture pixel review")
    args = parser.parse_args()
    if args.negative_review and args.kind != "complete_motion":
        parser.error("negative review probe requires complete_motion")
    value = run(args.case, args.kind, negative_review=args.negative_review)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
