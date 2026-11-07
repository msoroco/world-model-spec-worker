"""Eight unselected C110454 engineering alternatives and saved risk checks."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CASES = ("reference", "contrast")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")
BASE = {"route_tracking_lookahead_m": 6.0,
        "parking_brake_start_m": 12.0,
        "overview_fov_deg": 90.0,
        "rate_hz": 20, "duration_s": 24.0,
        "camera_profile": ["overview", "approach", "intersection", "parking"]}
CHANGES = {
    "primary": {},
    "fallback1": {"route_tracking_lookahead_m": 3.5},
    "fallback2": {"parking_brake_start_m": 17.0},
    "fallback3": {"overview_fov_deg": 105.0},
}
TRIGGERS = {
    "fallback1": {"metric": "max_route_cross_track_error_m", "op": ">", "threshold": .45,
                  "source": "original Native ego pose joined to authored route and map readback"},
    "fallback2": {"metric": "parking_endpoint_speed_m_s", "op": ">", "threshold": .3,
                  "source": "original Native velocity at surveyed parking endpoint"},
    "fallback3": {"metric": "min_ego_pixel_margin_px", "op": "<", "threshold": 40,
                  "source": "decoded original overview video and original body-mask corners"},
}


def parameters(case: str, candidate: str) -> dict:
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError("Unknown case or candidate")
    return {"case": case, "candidate": candidate,
            "knobs": BASE | CHANGES[candidate],
            "fallback_trigger": TRIGGERS.get(candidate),
            "source_status": "planned_original_native_or_video_not_observed"}


def controller_parameters(case: str, candidate: str):
    """Concrete controller knobs for one authored route and candidate."""
    from controller import EngineeringKnobs
    spec = parameters(case, candidate)["knobs"]
    return EngineeringKnobs(
        lookahead_base_m=spec["route_tracking_lookahead_m"],
        target_speed_mps=5.5,
        final_brake_mps2=1.5,
        final_margin_m=spec["parking_brake_start_m"] - 9.0,
    )


def evaluate_trigger(candidate: str, metrics: dict, source: Path,
                     expected_sha256: str) -> bool:
    if candidate not in TRIGGERS:
        raise ValueError("Only fallbacks have measured triggers")
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("Original source hash differs")
    record = json.loads(source.read_text())
    if record != metrics or record.get("source_kind") != "original_native_and_video":
        raise ValueError("Metrics are not bound to the original source")
    trigger = TRIGGERS[candidate]
    value = record.get(trigger["metric"])
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Missing measured fallback metric")
    return value > trigger["threshold"] if trigger["op"] == ">" else value < trigger["threshold"]
