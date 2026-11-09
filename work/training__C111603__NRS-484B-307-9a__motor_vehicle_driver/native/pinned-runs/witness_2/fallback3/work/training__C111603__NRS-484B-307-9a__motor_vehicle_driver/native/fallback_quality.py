"""Measured quality decisions for C111603, separate from legal applicability."""
import json
import math
from pathlib import Path

from build import FRAMES, RATE, check
from process_original import process


def request_measurements(bundle):
    """Measure authored timing and speed as synthetic preflight diagnostics."""
    bundle = Path(bundle)
    check(bundle)
    rows = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    assert len(rows) == FRAMES
    approach = [r for r in rows if r["requested_phase"] == "approach"]
    hold = [r for r in rows if r["requested_phase"] == "yield_hold"]
    movement = [r for r in rows if r["requested_phase"] == "intersection_movement"]
    if not approach or not hold or not movement:
        raise ValueError("Requested phase coverage incomplete")
    speeds = [math.dist(a["requested_ego_xyz_m"], b["requested_ego_xyz_m"]) * RATE
              for a, b in zip(approach, approach[1:])]
    if not speeds:
        raise ValueError("Approach too short for speed measurement")
    return {"source_kind": "synthetic_request_measurement",
            "approach_speed_mps": round(max(speeds), 4),
            "yield_hold_to_entry_window_s": round((movement[0]["frame"] - hold[0]["frame"]) / RATE, 4),
            "movement_frame": movement[0]["frame"],
            "camera_policy": json.loads((bundle / "config.json").read_text())["camera_policy"],
            "original_native_observed": False}


def decide(primary, *, allow_synthetic=False):
    """Return three distinct trigger decisions; never select a candidate."""
    kind = primary.get("source_kind")
    if kind != "original_native_quality" and not (allow_synthetic and
            kind == "synthetic_request_measurement"):
        raise ValueError("Original Native quality measurements required")
    for field in ("approach_speed_mps", "yield_hold_to_entry_window_s"):
        value = primary.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid measured " + field)
    visible = primary.get("signal_and_other_visible_fraction")
    if visible is None:
        if kind == "original_native_quality":
            raise ValueError("Original visibility measurement missing")
        visible = 1.0
    if type(visible) not in (int, float) or not math.isfinite(visible) or not 0 <= visible <= 1:
        raise ValueError("Invalid measured visibility fraction")
    if primary.get("camera_policy") != "standard":
        raise ValueError("Primary camera policy mismatch")
    if kind == "original_native_quality" and primary.get("original_native_observed") is not True:
        raise ValueError("Original provenance missing")
    metrics = {"approach_speed_mps": primary["approach_speed_mps"],
               "signal_and_other_visible_fraction": visible,
               "yield_hold_to_entry_window_s": primary["yield_hold_to_entry_window_s"]}
    return {"metrics": metrics,
            "triggers": {
                "fallback1": primary["approach_speed_mps"] > 7.0,
                "fallback2": visible < .9,
                "fallback3": primary["yield_hold_to_entry_window_s"] < 3.0},
            "source_kind": kind, "selected_candidate": None,
            "original_native_observed": kind == "original_native_quality",
            "legal_verdict": None, "delivery_ready": False}


def from_capture(bundle, directory, review_path, *, synthetic_fixture=False):
    """Derive quality metrics from validated actor/video/review capture sources."""
    bundle, directory, review_path = Path(bundle), Path(directory), Path(review_path)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    if cfg["candidate_id"] != "primary":
        raise ValueError("Fallback decisions require a primary capture")
    saved = process(bundle, directory, review_path, synthetic_fixture=synthetic_fixture)
    review = json.loads(review_path.read_text())
    visible_frames = review.get("quality_signal_other_visible_frames")
    if (not isinstance(visible_frames, list) or not visible_frames or
            any(type(frame) is not int or not 0 <= frame < FRAMES for frame in visible_frames) or
            len(set(visible_frames)) != len(visible_frames)):
        raise ValueError("Source-hashed visibility frame review missing or invalid")
    raw = [json.loads(line) for line in (directory / "native-raw-actors.jsonl").read_text().splitlines()]
    if len(raw) != FRAMES:
        raise ValueError("Capture row count changed")
    approach = [r for r in raw if r["requested_phase"] == "approach"]
    hold = [r for r in raw if r["requested_phase"] == "yield_hold"]
    if not approach or not hold:
        raise ValueError("Capture approach or hold missing")
    speed = max(r["ego"]["speed_mps"] for r in approach)
    entry = next((r for r in raw if r["frame"] > hold[0]["frame"] and
                  r["ego"]["center_native_xyz_m"][1] > -4.5), None)
    if entry is None:
        raise ValueError("Physical intersection entry not observed")
    receipt = {"source_kind": "synthetic_request_measurement" if synthetic_fixture else
               "original_native_quality",
               "approach_speed_mps": round(speed, 4),
               "yield_hold_to_entry_window_s": round((entry["frame"] - hold[0]["frame"]) / RATE, 4),
               "signal_and_other_visible_fraction": round(len(visible_frames) / FRAMES, 6),
               "camera_policy": cfg["camera_policy"],
               "raw_sha256": saved["raw_sha256"], "review_sha256": saved["review_sha256"],
               "original_native_observed": saved["original_native_observed"]}
    result = decide(receipt, allow_synthetic=synthetic_fixture)
    result["raw_sha256"] = receipt["raw_sha256"]
    result["review_sha256"] = receipt["review_sha256"]
    return result
