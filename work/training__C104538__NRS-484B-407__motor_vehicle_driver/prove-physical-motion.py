"""Exercise three physical-motion branches without inventing Native provenance."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

from physical_motion_audit import audit, check_lifecycle, classify, rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ("below_500_ft", "at_500_ft", "above_500_ft")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(call, expected: str) -> None:
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f"Wrong rejection: {error}") from error
    else:
        raise AssertionError("Expected rejection: " + expected)


def run() -> dict:
    cases = []
    for suffix in SUFFIXES:
        case = HERE.name + "__" + suffix
        attempt = ROOT / ".runtime-work" / f"c104538-final-{suffix}-primary-compat"
        if suffix == "below_500_ft":
            attempt = ROOT / ".runtime-work/c104538-final-below-primary-compat"
        diagnostic = audit(attempt, case, diagnostic=True)
        assert diagnostic["source_shaped_motion_status"] == "met"
        assert diagnostic["native_motion_status"] == "unverified"
        assert diagnostic["maneuver_completed"] is False
        rejects(lambda: audit(attempt, case), "Synthetic source cannot prove original Native motion")
        cases.append({"case_id": case, "source_shaped_status": "met",
                      "native_status": "unverified", "source_sha256": diagnostic["source_sha256"]})
    attempt = ROOT / ".runtime-work/c104538-final-below-primary-compat"
    history, trace, evidence, mapping = [rows(attempt/name) for name in
        ("native_body_history.jsonl", "trace.jsonl", "capture/evidence.jsonl",
         "video_frames.jsonl")]
    incomplete_history, incomplete_evidence = copy.deepcopy(history), copy.deepcopy(evidence)
    for body, capture in zip(incomplete_history, incomplete_evidence):
        body["ego_heading_deg"] = -90.0
        capture["ego"]["heading_deg"] = -90.0
    incomplete = classify(incomplete_history, trace, incomplete_evidence, mapping, 480)
    assert incomplete["status"] == "not_met" and not incomplete["engineering_reversal_observed"]
    damaged = copy.deepcopy(mapping)
    damaged[100]["native_frame"] += 1
    rejects(lambda: classify(history, trace, evidence, damaged, 480),
            "Original motion/frame/time join differs")
    with tempfile.TemporaryDirectory() as temporary:
        missing = audit(Path(temporary), HERE.name + "__below_500_ft", diagnostic=True)
    assert missing["motion_status"] == "unverified" and missing["missing_sources"]
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    assert check_lifecycle(events)["saved_processing_after_owner_release"] is True
    premature = events.copy()
    premature[-2:] = reversed(premature[-2:])
    rejects(lambda: check_lifecycle(premature),
            "Saved processing preceded Native ownership closure")
    report = {"format": "c104538-physical-motion-cpu-proof-v1",
              "diagnostic_complete_cases": cases,
              "incomplete_source_shaped_status": incomplete["status"],
              "missing_source_status": missing["motion_status"],
              "wrong_frame_rejected": True,
              "synthetic_as_native_rejected": True,
              "premature_saved_processing_rejected": True,
              "native_maneuver_completed": False,
              "physical_preparation_receipt_bound": False,
              "original_pixel_visibility_proven": False}
    path = HERE / "update018-physical-motion-cpu-proof.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return {"cases": len(cases), "proof_sha256": sha(path),
            "native_maneuver_completed": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
