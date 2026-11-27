"""Synthetic source-bound physical preparation for statutory variants.

This checks CPU fixture completeness and activity-specific rest. It does not
assert an original Native capture or a legal obstruction conclusion.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from statutory_measure import measure

EVENTS = ("capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lifecycle(events: list[str]) -> dict:
    if tuple(events) != EVENTS:
        raise ValueError("Saved processing precedes Native ownership closure")
    return {"events": list(EVENTS), "order_verified": True,
            "physical_capture_claimed": False}


def assess(root: Path) -> dict:
    root = Path(root)
    required = ("config.json", "native_samples.jsonl", "video_frames.jsonl",
                "camera-frames.jsonl", "obstruction-inventory.json")
    sources = {name: sha(root / name) for name in required if (root / name).is_file()}
    missing = [name for name in required if name not in sources]
    if "config.json" not in sources:
        raise ValueError("Physical fixture needs exact configuration source")
    cfg = json.loads((root / "config.json").read_text())
    case = cfg.get("case_id", "")
    if (cfg.get("cell_id") != "C135702" or cfg.get("law_id") != "NRS-484B-450-1k"
            or "__selected_statutory_" not in case):
        raise ValueError("Physical fixture selects another assignment")
    status = "unverified"
    observations = {}
    detail = {"missing_evidence": missing, "physical_causation_confirmed": False,
              "legal_verdict_claimed": False}
    if not missing:
        try:
            observations = measure(root / "native_samples.jsonl", sources["native_samples.jsonl"])
        except ValueError as error:
            if "sustained source rest and spatial sample" not in str(error):
                raise
            status = "not_met"
            detail["reason"] = str(error)
        else:
            status = "met"
            detail["rest_frames_at_requested_position"] = observations["rest_frames_at_requested_position"]
            detail["minimum_open_width_m"] = observations["minimum_open_width_m"]
    check = {"status": status,
             "method": "source-bound requested activity at highway obstruction",
             "intervals": [{"first_time_s": 0, "last_time_s": 29.95}] if status == "met" else [],
             "sources": sources, "details": detail, "missing_evidence": missing,
             "physical_causation_claimed": False, "legal_verdict_claimed": False}
    return {"format": "c135702-statutory-physical-fixture-v1", "case_id": case,
            "physical_checks": {"setup": dict(check), "target": dict(check), "maneuver": check},
            "realized_observables": {"rest_frames_at_requested_position": {
                "value": observations["rest_frames_at_requested_position"], "unit": "count",
                "source": "native_samples.jsonl"}} if status == "met" else {},
            "setup_confirmed": status == "met", "behavior_attempted": status == "met",
            "maneuver_completed": status == "met", "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "physical_causation_confirmed": False,
            "legal_verdict_claimed": False}
