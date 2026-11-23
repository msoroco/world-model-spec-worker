"""Document the partial source-bound measurement chain for both exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C150530__LVMC-11-60-090__taxi_driver"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    cases = []
    for suffix in ("near_stand", "far_stand"):
        map_path = ROOT / "candidates" / (suffix + ".xodr")
        cases.append({"case_id": ASSIGNMENT + "__" + suffix,
                      "candidate_map": "candidates/" + suffix + ".xodr",
                      "candidate_map_sha256": _sha(map_path),
                      "candidate_layout": "candidates/" + suffix + ".json"})
    code = {name: {"path": name, "sha256": _sha(ROOT / name)} for name in
            ("reviewed_context.py", "native_trace_capture.py",
             "turn_trace_finalizer.py", "taxi_native_motion.py")}
    return {
        "format": "c150530-partial-measurement-contract-v1",
        "assignment_id": ASSIGNMENT,
        "law_id": "LVMC-11-60-090",
        "law_source": {"path": "inputs/testing__C150530__LVMC-11-60-090__taxi_driver/assignment.json",
                       "sha256": "8b93441aae725dc0cc31fca5b5393289efa9d4ae0faedaae371ecb906a9"},
        "cases": cases,
        "source_files_per_attempt": ["original-trace.jsonl", "original-trace-seal.json",
                                     "reviewed-context.json", "reviewed_sources/"],
        "code": code,
        "selected_requirements": [
            {"disposition_index": 0, "requirement": "cab and qualifying designated stand",
             "context_sources": ["cab_license", "stand_designation", "stand_marking",
                                 "designation_provisions", "jurisdiction"],
             "measurement_outputs": ["stand_departure_frame"],
             "unresolved_review": "original document authority and designation applicability"},
            {"disposition_index": 1, "requirement": "posted notice of right-turn requirement",
             "context_sources": ["posted_notice"],
             "measurement_outputs": ["context_source_joins"],
             "unresolved_review": "original sign installation and actual camera pixels"},
            {"disposition_index": 2, "requirement": "right turn at first street intersection after departure",
             "context_sources": ["jurisdiction"],
             "measurement_outputs": ["first_intersection_entry_frame",
                                     "first_intersection_exit_frame", "turn_angle_deg",
                                     "engineering_right_turn_observed"],
             "unresolved_review": "actual Native motion, street identity and physical completion"},
        ],
        "status": "partial_cpu_component; no original source packet or pinned process-saved proof",
    }


if __name__ == "__main__":
    (ROOT / "measurement-contract.json").write_text(json.dumps(build(), indent=2) + "\n")
