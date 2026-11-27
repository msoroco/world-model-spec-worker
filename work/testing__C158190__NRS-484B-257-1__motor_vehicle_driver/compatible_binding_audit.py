"""Verify the only compatible yield-cell route without treating it as evidence.

This is a CPU allocation audit. It cannot authorize a new assignment, prove an
original recording, or turn C158190's stop-sign cell into a yield-sign cell.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ORIGIN = "testing__C158190__NRS-484B-257-1__motor_vehicle_driver"
TARGET = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"
NEAREST = {
    TARGET + "__nearest_view_response",
    TARGET + "__nearest_view_uninterrupted",
    TARGET + "__nearest_view_stopped",
}


def read(repo: Path, name: str) -> tuple[dict, str]:
    path = repo / name
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def audit(repo: Path) -> dict:
    origin, origin_sha = read(repo, f"inputs/{ORIGIN}/assignment.json")
    target, target_sha = read(repo, f"inputs/{TARGET}/assignment.json")
    catalog, catalog_sha = read(repo, "inputs/coverage/candidate-cells.json")
    batch, batch_sha = read(repo, "batch.json")
    plan, plan_sha = read(repo, f"work/{TARGET}/case-plan.json")
    manifest, manifest_sha = read(repo, f"work/{TARGET}/execution-manifest.json")
    result, result_sha = read(repo, f"work/{TARGET}/result.json")
    cells = {row["cell_id"]: row for row in catalog["cells"]}
    source, destination = cells["C158190"], cells["C158208"]
    if origin["assignment_id"] != ORIGIN or target["assignment_id"] != TARGET:
        raise ValueError("frozen assignment identity differs")
    if origin["law_id"] != target["law_id"] or origin["actor"] != target["actor"]:
        raise ValueError("law or actor differs")
    if source["control"] != "stop_sign" or destination["control"] != "yield_sign":
        raise ValueError("frozen control identities differ from the reviewed route")
    if (source["layout"], source["maneuver"]) != (destination["layout"], destination["maneuver"]):
        raise ValueError("layout or maneuver differs")
    if ORIGIN not in batch["assignments"] or TARGET not in batch["assignments"]:
        raise ValueError("an assignment is absent from the immutable batch")
    matching = [row["cell_id"] for row in catalog["cells"]
                if row["control"] == "yield_sign"
                and row["layout"] == source["layout"]
                and row["maneuver"] == source["maneuver"]
                and origin["actor"] in row["candidate_ego_parties"]]
    if matching != ["C158208"]:
        raise ValueError("compatible catalog inventory changed")
    selected = {row["case_id"] for row in manifest["cases"] if row.get("kind") == "delivery"}
    planned = {row["case_id"] for row in plan["cases"]}
    if not NEAREST.issubset(selected & planned):
        raise ValueError("compatible package lacks selected nearest-view cases")
    required_comparison = next((row for row in plan["comparisons"]
                                if row["comparison_id"] == "nearest_view_no_line_or_crosswalk"), None)
    if required_comparison is None or not NEAREST.issubset(set(required_comparison["case_ids"])):
        raise ValueError("compatible package lacks controlled nearest-view comparison")
    if result.get("status") != "ready" or result.get("readiness_kind") != "delivery_prepared":
        raise ValueError("compatible assignment has not passed its CPU readiness gate")
    if manifest["assignment_id"] != TARGET or result["assignment_id"] != TARGET:
        raise ValueError("compatible package identity differs")
    return {
        "format": "worker-compatible-binding-audit",
        "origin_assignment_id": ORIGIN,
        "target_assignment_id": TARGET,
        "origin_fixed_control": "stop_sign",
        "target_fixed_control": "yield_sign",
        "nearest_view_selected_case_ids": sorted(NEAREST),
        "comparison_id": "nearest_view_no_line_or_crosswalk",
        "conclusion": "C158208 has CPU-prepared the yield nearest-view branch; C158190's fixed stop-sign cell is a distinct control and cannot claim those captures or substitute its own yield diagnostics.",
        "original_physical_evidence": "unverified",
        "source_sha256": {
            "origin_assignment": origin_sha, "target_assignment": target_sha,
            "candidate_catalog": catalog_sha, "batch": batch_sha,
            "target_plan": plan_sha, "target_manifest": manifest_sha,
            "target_result": result_sha,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.repo.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
