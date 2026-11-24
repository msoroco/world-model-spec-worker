"""Classify synthetic motion fixtures without making a legal or Native claim."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from blind_encounter import CASE_BY_ID


def evaluate(case_id: str, fixture: dict, source_sha256: str) -> dict:
    case = CASE_BY_ID[case_id]
    required = ("frame_count", "hz", "approach_frame", "stop_frame", "proceed_frame",
                "contact_frame", "clear_frame", "speed_before_mps", "speed_during_mps",
                "speed_after_mps", "gap_start_m", "gap_at_encounter_m", "precaution_observed")
    base = {"case_id": case_id, "diagnostic_fixture": True,
            "provenance_kind": "synthetic_fixture", "source_sha256": source_sha256,
            "physical_acceptance": "not_assessed"}
    if any(key not in fixture for key in required):
        return dict(base, maneuver_completed=False, realized_observables={},
                    physical_checks={"maneuver": {"status": "unverified",
                                                  "method": "required synthetic source fields and 20 Hz timebase",
                                                  "sources": [source_sha256]}})
    if fixture["frame_count"] != 900 or fixture["hz"] != 20:
        raise ValueError("synthetic original capture timebase differs")
    for key in ("approach_frame", "stop_frame", "proceed_frame", "contact_frame", "clear_frame"):
        value = fixture[key]
        if value is not None and (type(value) is not int or not 0 <= value < 900):
            raise ValueError("synthetic event frame outside original window")
    motion = (fixture["approach_frame"] is not None and
              fixture["speed_before_mps"] > 0 and
              fixture["gap_start_m"] > fixture["gap_at_encounter_m"] >= 0)
    if case.response == "full_stop":
        motion &= fixture["stop_frame"] is not None and fixture["speed_during_mps"] <= 0.05
    else:
        motion &= fixture["speed_during_mps"] > 0.2
    if case.encounter == "contact":
        motion &= fixture["contact_frame"] is not None
    if case.precaution == "early_proceed":
        motion &= (fixture["proceed_frame"] is not None and
                   fixture["clear_frame"] is not None and
                   fixture["proceed_frame"] < fixture["clear_frame"])
    else:
        motion &= (fixture["proceed_frame"] is None or
                   fixture["clear_frame"] is not None and
                   fixture["proceed_frame"] >= fixture["clear_frame"])
    result = dict(base, maneuver_completed=bool(motion),
                  realized_observables={"speed_before_mps": fixture["speed_before_mps"],
                                        "gap_at_encounter_m": fixture["gap_at_encounter_m"],
                                        "precaution_observed": fixture["precaution_observed"]},
                  physical_checks={"maneuver": {"status": "met" if motion else "not_met",
                                                "method": "synthetic event-order and sampled-motion check; no legal verdict",
                                                "sources": [source_sha256]}})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.fixture.read_bytes()
    result = evaluate(args.case, json.loads(source), hashlib.sha256(source).hexdigest())
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["physical_checks"]["maneuver"]["status"])


if __name__ == "__main__":
    main()
