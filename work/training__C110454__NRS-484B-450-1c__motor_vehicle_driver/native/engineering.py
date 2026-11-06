"""Four concrete, law-preserving construction settings per parking probe."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

CASES = ("probe_a", "probe_b")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")
BASE = {"route_lookahead_m": 5.0, "parking_brake_margin_m": 3.5,
        "overview_fov_deg": 90.0, "rate_hz": 20, "duration_s": 24}
CHANGES = {"primary": {}, "fallback1": {"route_lookahead_m": 3.0},
           "fallback2": {"parking_brake_margin_m": 6.0},
           "fallback3": {"overview_fov_deg": 105.0}}
TRIGGERS = {
    "fallback1": {"metric": "max_cross_track_error_m", "op": ">", "threshold": 0.45,
                  "source": "original Native pose joined to surveyed lane and authored route"},
    "fallback2": {"metric": "mean_final_park_speed_m_s", "op": ">", "threshold": 0.2,
                  "source": "original Native velocity during final 2 s at the target footprint"},
    "fallback3": {"metric": "min_vehicle_pixel_margin_px", "op": "<", "threshold": 40,
                  "source": "decoded original synchronized overview video and body mask"},
}


def parameters(case: str, candidate: str) -> dict:
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError("Unknown case or construction")
    return {"case": case, "candidate": candidate, "knobs": BASE | CHANGES[candidate],
            "fallback_trigger": TRIGGERS.get(candidate),
            "source_status": "original Native and pixels pending"}


def controller_parameters(case: str, candidate: str):
    from controller import EngineeringKnobs
    spec = parameters(case, candidate)["knobs"]
    return EngineeringKnobs(lookahead_base_m=spec["route_lookahead_m"],
                            target_speed_mps=4.5, final_brake_mps2=1.5,
                            final_margin_m=spec["parking_brake_margin_m"])


def evaluate_trigger(candidate: str, source: Path, expected_sha256: str) -> bool:
    if candidate not in TRIGGERS:
        raise ValueError("Only fallback triggers are measurable")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Trigger source hash differs")
    record = json.loads(raw)
    if record.get("source_kind") != "original_native_and_video":
        raise ValueError("Trigger metric lacks original source provenance")
    trigger = TRIGGERS[candidate]
    value = record.get(trigger["metric"])
    if type(value) not in (int, float):
        raise ValueError("Missing measured trigger metric")
    return value > trigger["threshold"] if trigger["op"] == ">" else value < trigger["threshold"]
