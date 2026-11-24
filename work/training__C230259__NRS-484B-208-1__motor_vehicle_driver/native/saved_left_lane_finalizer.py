"""Saved-only exact-case finalization of retained left-lane relation sources."""

import hashlib
import json
from pathlib import Path

from left_lane_measure import measure, sha


ASSIGNMENT = "training__C230259__NRS-484B-208-1__motor_vehicle_driver"
SOURCES = ("native-actors.jsonl", "native-road-context.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finalize(attempt, seal):
    attempt = Path(attempt)
    require(seal.get("case_id") in
            (ASSIGNMENT + "__reference", ASSIGNMENT + "__contrast"),
            "Exact left-lane case required")
    require(seal.get("candidate_id") == "primary" and
            seal.get("native_exit_code") == 0, "Completed primary Native acquisition required")
    require(set(seal.get("source_sha256", {})) == set(SOURCES),
            "Complete saved source inventory required")
    measured = measure(attempt / SOURCES[0], attempt / SOURCES[1], seal["source_sha256"])
    require(measured["source_kind"] == seal.get("source_kind"),
            "Sealed source provenance differs")
    return {"format": "c230259-saved-left-lane-finalization-v1",
            "case_id": seal["case_id"], "candidate_id": "primary",
            "recorded_only": True, "source_kind": measured["source_kind"],
            "source_sha256": seal["source_sha256"],
            "sample_count": measured["sample_count"],
            "capture_hz": measured["capture_hz"],
            "measurements": {key: measured[key] for key in
                             ("rear_higher_speed_behind_frames", "overtake_crossing_frame",
                              "slow_extreme_left_frames", "slow_extreme_left_after_overtake_frames",
                              "ego_exited_left_before_crossing")},
            "controlled_access_verified": False,
            "posted_limit_original_verified": False,
            "driver_knowledge_or_reasonable_notice": None,
            "subsection_2_exception_review": None,
            "legal_verdict": None, "accepted": False,
            "physical_completion_claimed": False}
