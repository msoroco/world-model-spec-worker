"""Measured fallback policies and controlled construction parameters."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")
CASES = ("probe_a", "probe_b")


def candidate_plan(case: str, candidate: str) -> dict:
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError("Unknown case or candidate")
    path = ROOT / "draft-candidates.json"
    raw = path.read_bytes()
    plan = json.loads(raw)
    matching = [row for row in plan["cases"] if row["case_id"].endswith("__" + case)]
    if len(matching) != 1:
        raise ValueError("Controlled case absent")
    case_row = matching[0]
    rows = [row for row in case_row["candidates"] if row["name"] == candidate]
    if len(rows) != 1:
        raise ValueError("Construction candidate absent")
    knobs = {k: v for k, v in rows[0].items() if k != "name"}
    knobs.update({"sample_rate_hz": 20, "duration_s": 24,
                  "camera_profile": ["overview", "ego_forward", "ego_side", "junction"],
                  "speed_pid_kp": .55, "brake_pid_kp": .55,
                  "steering_lookahead_m": 10.0})
    canonical = json.dumps({"case_id": case_row["case_id"], "candidate": candidate,
                            "knobs": knobs}, sort_keys=True, separators=(",", ":")).encode()
    return {"case_id": case_row["case_id"], "candidate": candidate,
            "target_relation": case_row["target_relation"], "knobs": knobs,
            "construction_sha256": hashlib.sha256(canonical).hexdigest(),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "fallback_trigger": case_row["fallback_trigger"],
            "selected": False}


def target_mph(case: str, candidate: str, native_y_m: float) -> float:
    """Controller target from Native y, normalized to authored approach y."""
    plan = candidate_plan(case, candidate)
    k = plan["knobs"]
    if case == "probe_b":
        return float(k["hold_mph"])
    y = -native_y_m
    start, finish, target = (float(k[n]) for n in
                              ("brake_start_y_m", "brake_finish_y_m", "target_mph"))
    if not start < finish < -7 or not 0 < target < 30:
        raise ValueError("Invalid approach reduction profile")
    if y <= start:
        return 30.0
    if y >= finish:
        return target
    return 30.0 + (target - 30.0)*(y-start)/(finish-start)


def evaluate_fallback(case: str, candidate: str, source_path: Path,
                      expected_sha256: str) -> dict:
    """Read the saved source before selecting the next engineering candidate."""
    if candidate not in CANDIDATES:
        raise ValueError("Unknown construction candidate")
    from measure_approach import measure
    measurement = measure(source_path, expected_sha256)
    relation = measurement.get("measured_relation")
    if case == "probe_a":
        triggered = relation != "measured_early_decrease_held"
        reason = "early speed reduction or crossing hold below engineering surrogate"
    elif case == "probe_b":
        triggered = relation != "measured_no_material_decrease"
        reason = "held-speed comparison differs from measured target"
    else:
        raise ValueError("Unknown controlled case")
    index = CANDIDATES.index(candidate)
    next_candidate = CANDIDATES[index+1] if triggered and index+1 < len(CANDIDATES) else candidate
    return {"triggered": triggered, "reason": reason,
            "candidate": candidate, "next_candidate": next_candidate,
            "exhausted": triggered and index+1 == len(CANDIDATES),
            "source_sha256": measurement.get("source_sha256"),
            "measured_relation": relation, "legal_verdict": None}
