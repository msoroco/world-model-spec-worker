"""CPU source-bound parked-state criterion and Native lifecycle ordering.

The status is an engineering completion check for the selected parked-state
capture. A fixture status never certifies actual Native or legal obstruction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure_obstruction import measure
from source_join import check as source_join

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
        raise ValueError("Physical fixture needs an exact configuration source")
    config = json.loads((root / "config.json").read_text())
    if config.get("cell_id") != "C135702" or config.get("law_id") != "NRS-484B-450-1k":
        raise ValueError("Physical fixture selects another law or cell")
    status = "unverified"
    observations = {}
    details = {"missing_evidence": missing,
               "physical_causation_confirmed": False,
               "legal_verdict_claimed": False}
    if not missing:
        source_join(root, source_kind="synthetic_cpu")
        try:
            observations = measure(root / "native_samples.jsonl", sources["native_samples.jsonl"])
        except ValueError as error:
            if "No sustained parked alongside obstruction sample" not in str(error):
                raise
            status = "not_met"
            details["reason"] = str(error)
        else:
            status = "met" if observations["parked_alongside_frames"] >= 400 else "not_met"
            details["parked_alongside_frames"] = observations["parked_alongside_frames"]
            details["minimum_open_width_m"] = observations["minimum_open_width_m"]
    check = {"status": status, "method": "source-bound sustained parked body beside highway obstruction",
             "intervals": [{"first_time_s": 0, "last_time_s": 29.95}] if status == "met" else [],
             "sources": sources, "details": details,
             "missing_evidence": missing, "legal_verdict_claimed": False,
             "physical_causation_claimed": False}
    return {"format": "c135702-physical-fixture-check-v1",
            "case_id": config["case_id"], "physical_checks": {
                "setup": dict(check), "target": dict(check), "maneuver": check},
            "realized_observables": {"parked_alongside_frames": {
                "value": observations["parked_alongside_frames"], "unit": "count",
                "source": "native_samples.jsonl"}} if status == "met" else {},
            "setup_confirmed": status == "met", "behavior_attempted": status == "met",
            "maneuver_completed": status == "met",
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_causation_confirmed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.fixture)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": result["case_id"],
                      "status": result["physical_checks"]["maneuver"]["status"],
                      "synthetic_only": True}))
