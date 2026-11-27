"""Audit the immutable officer-control exception versus sign-governed branch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ORIGIN = "testing__C157964__NRS-484B-257-2__motor_vehicle_driver"
TARGET = "testing__C158208__NRS-484B-257-2__motor_vehicle_driver"
REQUIRED = ("occupied_response", "approaching_near_response", "approaching_far_response",
            "approaching_near_uninterrupted", "approaching_near_speed_below",
            "approaching_near_speed_inside", "approaching_near_speed_above")
COMPARISONS = ("occupied_vs_approaching", "approach_station_sweep",
               "response_vs_uninterrupted", "approaching_near_crossing_speed_sweep")


def read(repo: Path, relative: str) -> tuple[dict, str]:
    raw = (repo / relative).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def audit(repo: Path) -> dict:
    paths = {
        "origin_assignment": f"inputs/{ORIGIN}/assignment.json",
        "origin_witness": f"inputs/{ORIGIN}/witnesses.json",
        "target_assignment": f"inputs/{TARGET}/assignment.json",
        "catalog": "inputs/coverage/candidate-cells.json",
        "batch": "batch.json",
        "target_plan": f"work/{TARGET}/case-plan.json",
        "target_manifest": f"work/{TARGET}/execution-manifest.json",
        "target_result": f"work/{TARGET}/result.json",
    }
    sources = {key: read(repo, value) for key, value in paths.items()}
    origin = sources["origin_assignment"][0]
    witness = sources["origin_witness"][0]
    target = sources["target_assignment"][0]
    cells = {row["cell_id"]: row for row in sources["catalog"][0]["cells"]}
    batch = sources["batch"][0]
    plan, manifest, result = (sources[key][0] for key in
                              ("target_plan", "target_manifest", "target_result"))
    if origin["assignment_id"] != ORIGIN or target["assignment_id"] != TARGET:
        raise ValueError("assignment identity differs")
    if origin["law_id"] != target["law_id"] or origin["actor"] != target["actor"]:
        raise ValueError("law or actor differs")
    law = origin["law"]["text"]
    if not law.startswith("Except when traffic is being controlled by a police officer or a traffic-control signal:"):
        raise ValueError("officer exception no longer matches the original law")
    if cells["C157964"]["control"] != "police_officer" or cells["C158208"]["control"] != "yield_sign":
        raise ValueError("frozen control split differs")
    if origin["actor"] not in cells["C158208"]["candidate_ego_parties"]:
        raise ValueError("target actor is ineligible")
    if ORIGIN not in batch["assignments"] or TARGET not in batch["assignments"]:
        raise ValueError("source or target not assigned in immutable batch")
    if len(witness) != 1 or witness[0]["binding"]["original_assignment_id"] != TARGET:
        raise ValueError("frozen supplemental binding differs")
    if witness[0]["binding"]["assignment_id"] != ORIGIN:
        raise ValueError("frozen supplemental assignment differs")
    required = {TARGET + "__" + suffix for suffix in REQUIRED}
    selected = {row["case_id"] for row in manifest["cases"] if row.get("kind") == "delivery"}
    planned = {row["case_id"] for row in plan["cases"]}
    if not required.issubset(selected & planned):
        raise ValueError("target lacks selected within/approaching cases")
    pairs = {row["comparison_id"]: row for row in plan["comparisons"]}
    if not set(COMPARISONS).issubset(pairs):
        raise ValueError("target lacks controlled branch comparisons")
    if not all(set(pairs[name]["case_ids"]).issubset(required) and
               len(pairs[name]["case_ids"]) >= 2 for name in COMPARISONS):
        raise ValueError("comparison membership differs from selected cases")
    if result.get("status") != "ready" or result.get("readiness_kind") != "delivery_prepared":
        raise ValueError("target CPU readiness is not current")
    if manifest["assignment_id"] != TARGET or result["assignment_id"] != TARGET:
        raise ValueError("target package identity differs")
    return {
        "format": "worker-officer-exception-binding-audit",
        "origin_assignment_id": ORIGIN,
        "target_assignment_id": TARGET,
        "fixed_origin_control": "police_officer",
        "target_control": "yield_sign",
        "selected_target_case_ids": sorted(required),
        "target_comparison_ids": list(COMPARISONS),
        "original_physical_evidence": "unverified",
        "conclusion": "The current C158208 CPU package covers the sign-governed within/approaching branch. C157964 is officer-controlled, an express exception in the exact law, and cannot claim the sign-governed duty under its frozen control.",
        "source_sha256": {key: value[1] for key, value in sources.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.repo.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
