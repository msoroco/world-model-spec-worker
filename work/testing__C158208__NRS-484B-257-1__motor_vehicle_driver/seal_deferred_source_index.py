"""Bind exact source-gated construction and pinned offline CPU receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_semantic_proposals import KINDS


HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal() -> dict:
    expected = {HERE.name + "__" + kind for kind in KINDS}
    plan = json.loads((HERE / "case-plan.json").read_text())
    if {row["case_id"] for row in plan["cases"]} != expected:
        raise ValueError("source-gated construction plan is incomplete")
    rows = []
    for kind in sorted(KINDS):
        case_id = HERE.name + "__" + kind
        candidate_rows = []
        for candidate, target_speed in (("primary", 4.0), ("fallback1", 3.5)):
            construction = HERE / "cases" / kind / (
                "construction-source-gated.json" if candidate == "primary" else
                "fallback1/construction-source-gated.json")
            log = HERE / ("cpu-nov26c-deferred-" + kind +
                          ("-offline.log" if candidate == "primary" else
                           "-fallback1-offline.log"))
            spec = json.loads(construction.read_text())
            receipt = json.loads(log.read_text())
            if (spec["case_id"] != case_id or spec.get("diagnostic_only") is not False or
                    receipt.get("case_id") != case_id or receipt.get("candidate_id") != candidate or
                    receipt.get("offline_passed") is not True or
                    receipt.get("simulation_started") is not False):
                raise ValueError("source-gated bundle or pinned offline proof differs: " + kind)
            files = {item["path"]: item["content"] for item in spec["files"]}
            scene = json.loads(files["scene.json"])
            config = json.loads(files["config.json"])
            if (scene.get("source_kind") != "local_review_required" or
                    scene.get("case_plan_sha256") != sha(HERE / "case-plan.json") or
                    files["runner.py"] != (HERE / "deferred_source_runner.py").read_text() or
                    config.get("candidate_target_speed_mps") != target_speed):
                raise ValueError("source gate or engineering fallback differs: " + kind)
            candidate_rows.append({"id": candidate,
                                   "construction": str(construction.relative_to(HERE)),
                                   "construction_sha256": sha(construction),
                                   "offline_log": log.name,
                                   "offline_log_sha256": sha(log)})
        rows.append({"case_id": case_id, "candidates": candidate_rows,
                     "original_source_status": "required_before_native_capture",
                     "physical_acceptance_claimed": False})
    output = {
        "format": "c158208-deferred-source-cpu-index-v1",
        "assignment_id": HERE.name,
        "status": "source_gated_constructions_offline_proven_not_delivery_selected",
        "plan_sha256": sha(HERE / "case-plan.json"),
        "runner_sha256": sha(HERE / "deferred_source_runner.py"),
        "cases": rows,
        "physical_acceptance_claimed": False,
        "legal_acceptance_claimed": False,
    }
    path = HERE / "deferred-source-cpu-index.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    return {"cases": len(rows), "candidate_constructions": 2 * len(rows),
            "sha256": sha(path)}


if __name__ == "__main__":
    print(json.dumps(seal(), indent=2))
