"""Evidence triad for opposing motion; diagnostic results are never acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from opposing_pass import measure


def assess(trace_path, expected_sha256):
    path = Path(trace_path)
    sources = {"opposing-actor-trace.json": expected_sha256}
    method = "original 20 Hz body overlap and opposite signed velocities"
    def outcome(status, reason, values=None):
        return {"physical_checks": {"maneuver": {"status": status,
            "method": method, "sources": sources, "reason": reason}},
            "maneuver_completed": status == "met",
            "realized_observables": values or {},
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}
    if not path.is_file():
        return outcome("unverified", "original actor trace missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        return outcome("unverified", "original actor trace hash changed")
    try:
        trace = json.loads(raw)
        measured = measure(trace)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        if str(exc) in ("no measured passing interval",
                        "opposing actual travel not established during passing"):
            return outcome("not_met", str(exc))
        return outcome("unverified", "original measurement source incomplete: " + str(exc))
    passing = measured["passing_frames"]
    if len(passing) < 2:
        return outcome("not_met", "fewer than two observed passing frames")
    return outcome("met", "opposing body overlap measured on original samples", {
        "passing_frame_count": {"value": len(passing), "unit": "frames",
            "method": method, "reference": "opposing-actor-trace.json"},
        "right_of_other_all": {"value": measured["right_of_other_all"],
            "unit": "boolean", "method": method, "reference": "opposing-actor-trace.json"}})
