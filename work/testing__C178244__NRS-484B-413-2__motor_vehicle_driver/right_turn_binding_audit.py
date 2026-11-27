"""Source-sealed CPU audit of the selected right-turn route."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ORIGIN = "testing__C178244__NRS-484B-413-2__motor_vehicle_driver"
TARGET = "testing__C378304__NRS-484B-413-2__motor_vehicle_driver"
SUFFIXES = ("short80", "continuous100", "above101", "interrupted", "rain")
COMPARISONS = ("business_right_distance", "signal_continuity", "regardless_weather")


def read(repo: Path, relative: str) -> tuple[dict, str]:
    raw = (repo / relative).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def audit(repo: Path) -> dict:
    paths = {
        "origin_input": f"inputs/{ORIGIN}/assignment.json",
        "target_input": f"inputs/{TARGET}/assignment.json",
        "catalog": "inputs/coverage/candidate-cells.json",
        "batch": "batch.json",
        "target_plan": f"work/{TARGET}/case-plan.json",
        "target_manifest": f"work/{TARGET}/execution-manifest.json",
        "target_result": f"work/{TARGET}/result.json",
    }
    sources = {key: read(repo, value) for key, value in paths.items()}
    origin, target = sources["origin_input"][0], sources["target_input"][0]
    catalog, batch = sources["catalog"][0], sources["batch"][0]
    plan, manifest, result = (sources[key][0] for key in
                              ("target_plan", "target_manifest", "target_result"))
    cells = {row["cell_id"]: row for row in catalog["cells"]}
    a, b = cells["C178244"], cells["C378304"]
    if origin["assignment_id"] != ORIGIN or target["assignment_id"] != TARGET:
        raise ValueError("frozen assignment identity differs")
    if origin["law_id"] != target["law_id"] or origin["actor"] != target["actor"]:
        raise ValueError("law or actor differs")
    if a["maneuver"] != "left_turn" or b["maneuver"] != "right_turn":
        raise ValueError("frozen turn-direction conflict changed")
    if b["layout"] != "business_district" or origin["actor"] not in b["candidate_ego_parties"]:
        raise ValueError("target district or actor compatibility changed")
    if ORIGIN not in batch["assignments"] or TARGET not in batch["assignments"]:
        raise ValueError("target is not an existing immutable-batch assignment")
    selected = {row["case_id"] for row in manifest["cases"] if row.get("kind") == "delivery"}
    required = {TARGET + "__" + suffix for suffix in SUFFIXES}
    planned = {row["case_id"] for row in plan["cases"]}
    if not required.issubset(selected & planned):
        raise ValueError("target selected cases do not cover the business right-turn boundary")
    comparisons = {row["comparison_id"]: row for row in plan["comparisons"]}
    if not set(COMPARISONS).issubset(comparisons):
        raise ValueError("target controlled comparisons incomplete")
    if not all(set(comparisons[name]["case_ids"]).issubset(required) and
               len(comparisons[name]["case_ids"]) >= 2 for name in COMPARISONS):
        raise ValueError("target comparison members differ from selected boundary cases")
    if result.get("status") != "ready" or result.get("readiness_kind") != "delivery_prepared":
        raise ValueError("target CPU readiness is not current")
    if manifest["assignment_id"] != TARGET or result["assignment_id"] != TARGET:
        raise ValueError("target package identity differs")
    return {
        "format": "worker-right-turn-binding-audit",
        "origin_assignment_id": ORIGIN,
        "target_assignment_id": TARGET,
        "frozen_origin_maneuver": a["maneuver"],
        "target_maneuver": b["maneuver"],
        "selected_target_case_ids": sorted(required),
        "comparison_ids": list(COMPARISONS),
        "original_physical_evidence": "unverified",
        "conclusion": "C378304 has CPU-prepared the business-district right-turn branch. C178244's six accepted left-turn metadata records cannot establish that right-turn branch or be relabeled.",
        "source_sha256": {key: value[1] for key, value in sources.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.repo.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
