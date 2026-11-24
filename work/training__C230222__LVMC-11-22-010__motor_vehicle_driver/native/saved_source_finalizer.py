"""Finalize retained source cues while leaving driver attention unresolved."""

import argparse
import hashlib
import json
from pathlib import Path

from attention_observation import measure


SOURCES = ("native-ego-frames.jsonl", "video_frames.jsonl",
           "native-driving-context.json", "overview.mkv", "approach.mkv",
           "reference_corner.mkv", "driver_reference.mkv")
ASSIGNMENT = "training__C230222__LVMC-11-22-010__motor_vehicle_driver"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finalize(attempt, seal):
    attempt = Path(attempt)
    seal = dict(seal)
    require(seal.get("case_id") in
            (ASSIGNMENT + "__reference", ASSIGNMENT + "__contrast"),
            "Exact saved case identity required")
    require(seal.get("candidate_id") == "primary" and
            seal.get("native_exit_code") == 0, "Completed primary Native source required")
    require(set(seal.get("source_sha256", {})) == set(SOURCES),
            "Complete sealed source inventory required")
    for name in SOURCES:
        require((attempt / name).is_file() and
                sha(attempt / name) == seal["source_sha256"][name],
                "Sealed saved source differs: " + name)
    observed = measure(attempt)
    require(observed["sample_count"] == 600 and
            set(observed["camera_decode"]) ==
            {"overview", "approach", "reference_corner", "driver_reference"},
            "Complete saved source observation required")
    require(observed["source_kind"] == seal.get("source_kind"),
            "Sealed provenance differs")
    require(all(observed["source_hashes"][name] == seal["source_sha256"][name]
                for name in SOURCES[:3]), "Measured source hashes differ")
    return {"format": "c230222-saved-source-finalization-v1",
            "case_id": seal["case_id"], "candidate_id": "primary",
            "recorded_only": True, "source_kind": observed["source_kind"],
            "source_sha256": seal["source_sha256"],
            "sample_count": observed["sample_count"],
            "sampling_rate_hz": observed["sampling_rate_hz"],
            "camera_decode": observed["camera_decode"],
            "speed_min_mps": min(observed["measurements"]["ego_speed"]),
            "speed_max_mps": max(observed["measurements"]["ego_speed"]),
            "driver_attention_to_operation": None,
            "attention_review_required": True,
            "legal_verdict": None, "accepted": False,
            "physical_completion_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = finalize(args.attempt, json.loads(args.seal.read_text()))
    args.output.write_text(json.dumps(output, indent=2) + "\n")
