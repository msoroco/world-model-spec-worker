"""Measured quality decisions for C111603, separate from legal applicability."""
import json
import math
from pathlib import Path

from build import FRAMES, RATE, check


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
            "signal_to_entry_window_s": round((movement[0]["frame"] - hold[0]["frame"]) / RATE, 4),
            "movement_frame": movement[0]["frame"],
            "camera_policy": json.loads((bundle / "config.json").read_text())["camera_policy"],
            "original_native_observed": False}


def decide(primary, *, allow_synthetic=False):
    """Return three distinct trigger decisions; never select a candidate."""
    kind = primary.get("source_kind")
    if kind != "original_native_quality" and not (allow_synthetic and
            kind == "synthetic_request_measurement"):
        raise ValueError("Original Native quality measurements required")
    for field in ("approach_speed_mps", "signal_to_entry_window_s"):
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
               "signal_to_entry_window_s": primary["signal_to_entry_window_s"]}
    return {"metrics": metrics,
            "triggers": {
                "fallback1": primary["approach_speed_mps"] > 7.0,
                "fallback2": visible < .9,
                "fallback3": primary["signal_to_entry_window_s"] < 3.0},
            "source_kind": kind, "selected_candidate": None,
            "original_native_observed": kind == "original_native_quality",
            "legal_verdict": None, "delivery_ready": False}
