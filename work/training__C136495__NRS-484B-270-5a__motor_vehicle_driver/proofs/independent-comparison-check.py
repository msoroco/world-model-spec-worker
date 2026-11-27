"""Independent saved-source isolation audit for the two due-care response probes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(early: Path, later: Path) -> dict:
    bindings = [json.loads((root / "rider-binding.json").read_text())
                for root in (early, later)]
    expected = ("early_response", "later_response")
    if tuple(b.get("condition") for b in bindings) != expected:
        raise ValueError("Comparison condition or ordering differs")
    if bindings[0].get("candidate_id") != bindings[1].get("candidate_id"):
        raise ValueError("Comparison candidate engineering differs")
    if bindings[0].get("fixed_context") != bindings[1].get("fixed_context"):
        raise ValueError("Comparison fixed road/actor/camera context differs")
    files = ("road.xodr", "actor-frames.jsonl", "camera-frame-map.jsonl",
             "classification.json", "collision-events.jsonl")
    if any(digest(early / name) != digest(later / name) for name in files):
        raise ValueError("Comparison changed a fixed original source")
    commands = [rows(root / "response-control.jsonl") for root in (early, later)]
    if any(len(stream) != 600 for stream in commands):
        raise ValueError("Comparison lacks full response-control source")
    differing = []
    for i, (a, b) in enumerate(zip(*commands)):
        if (a.get("native_frame") != b.get("native_frame") or
                a.get("time_s") != b.get("time_s") or
                a.get("source_forward_gap_m") != b.get("source_forward_gap_m") or
                a.get("source_ego_speed_mps") != b.get("source_ego_speed_mps")):
            raise ValueError("Comparison changed measured response inputs")
        if a.get("command") != b.get("command"):
            if not (12 < a["source_forward_gap_m"] <= 25 and
                    a["command"]["brake"] > 0 and
                    b["command"]["brake"] == 0):
                raise ValueError("Comparison changed command outside declared response band")
            differing.append(i)
    if not differing:
        raise ValueError("Comparison response setting had no exercised contrast")
    return {"format": "c136495-due-care-independent-comparison-v1",
            "case_ids": [b["case_id"] for b in bindings],
            "fixed_source_sha256": {name: digest(early / name) for name in files},
            "response_source_sha256": [digest(root / "response-control.jsonl")
                                        for root in (early, later)],
            "differing_command_frames": len(differing),
            "comparison_variable": "requested_longitudinal_response_trigger_distance",
            "physical_native_verified": False, "legal_due_care_conclusion": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--early", required=True)
    parser.add_argument("--later", required=True)
    parser.add_argument("--receipt")
    args = parser.parse_args()
    result = audit(Path(args.early), Path(args.later))
    if args.receipt:
        path = Path(args.receipt)
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
