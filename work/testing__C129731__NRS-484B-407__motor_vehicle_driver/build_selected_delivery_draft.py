"""Bind exact planned distance probes to their current Native source code.

This is a truthful draft until original accepted sources, the reviewed site,
four-view capture and canonical compatibility proofs are present.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sight_measurement import ASSIGNMENT
from native_case_constructor import DISTANCE_TARGETS_FT


SCRIPTS = ("native_case_constructor.py", "reversal_route_controller.py",
           "reversal_phase.py", "carla_sight_adapter.py",
           "native_sight_cameras.py",
           "native_camera_audit.py",
           "native_sight_capture.py", "distance_probe_audit.py",
           "sight_measurement.py", "selected_delivery.py",
           "delivery_audit.py", "comparison_audit.py",
           "build_exact_bundles.py", "selected_analysis.py")
MEASUREMENT = "selected-measurement-contract.draft.json"


def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(package: Path) -> dict:
    package = Path(package)
    plan = json.loads((package / "case-plan.json").read_text())
    proposal = json.loads((package / "proposals/cases.json").read_text())
    if plan.get("assignment_id") != ASSIGNMENT:
        raise ValueError("exact assignment identity changed")
    cases = plan.get("cases", [])
    drafts = proposal.get("cases", [])
    if (len(cases) != 4 or len(drafts) != 4 or
            [c["case_id"] for c in cases] != [c["case_id"] for c in drafts]):
        raise ValueError("four exact planned case identities required")
    script_hashes = {name: _sha(package / name) for name in SCRIPTS}
    diagnostic = json.loads((package / "execution-manifest.draft.json").read_text())
    diagnostic_index = {row["case_id"]: row for row in diagnostic.get("cases", [])}
    if len(diagnostic_index) != 4 or diagnostic.get("assignment_id") != ASSIGNMENT:
        raise ValueError("four exact diagnostic constructions required")
    entries = []
    for case, semantic in zip(cases, drafts):
        cid = case["case_id"]
        suffix = cid.removeprefix(ASSIGNMENT + "__")
        target = DISTANCE_TARGETS_FT.get(suffix)
        requested = semantic.get("variable_assignments", {}).get(
            "approaching_vehicle_distance", {}).get("value")
        if (not cid.startswith(ASSIGNMENT + "__") or target is None or
                requested != target or
                case.get("planning_status") != "source_review_pending" or
                case.get("gap_ids") != ["unverified-law-coverage"]):
            raise ValueError("unresolved distance case changed or was mislabeled")
        built = diagnostic_index.get(cid)
        if (not isinstance(built, dict) or
                _sha(package / built["construction"]) != built["construction_sha256"] or
                json.loads((package / built["construction"]).read_text()).get("diagnostic_only") is not True):
            raise ValueError("exact diagnostic construction changed")
        entries.append({
            "case_id": cid, "kind": "delivery_planned_source_pending",
            "target_first_turn_distance_ft": target,
            "source_site": {"status": "reviewed_packet_missing",
                            "required_fields": ["map_source_sha256", "observer_stations",
                                                "terrain_hit_labels", "subject_body_hit_labels",
                                                "case_setups"]},
            "native_construction": {"entrypoint": "native_case_constructor.py",
                                    "route_controller": "reversal_route_controller.py",
                                    "sight_capture": "carla_sight_adapter.py",
                                    "physical_realization": "unverified"},
            "post_capture": {"recorded_only": True,
                             "measurement": "sight_measurement.py",
                             "distance_probe_audit": "distance_probe_audit.py",
                             "delivery_audit": "delivery_audit.py",
                             "original_media_review": "selected_delivery.py"},
            "candidate_risk": case["physical_risk"],
            "diagnostic_construction": built["construction"],
            "diagnostic_construction_sha256": built["construction_sha256"],
            "measurement_analysis": "selected_analysis.py",
            "measurement_contract_draft": MEASUREMENT,
            "measurement_contract_sha256": _sha(package / MEASUREMENT),
            "offline_proof": "diagnostic_only_passed; selected delivery proof pending",
            "compatibility_proof": "pending_exact_bundle_and_sources",
            "delivery_acceptance": "pending_original_sources_and_review",
            "legal_visibility_judgment": "unresolved",
        })
    comparisons = plan.get("comparisons", [])
    if (len(comparisons) != 1 or comparisons[0].get("comparison_id") != "distance_500ft" or
            comparisons[0].get("case_ids") != [c["case_id"] for c in cases]):
        raise ValueError("exact distance comparison changed")
    return {"format": "c129731-selected-delivery-draft-v1",
            "assignment_id": ASSIGNMENT,
            "status": "source_review_pending",
            "source_code_sha256": script_hashes,
            "case_plan_sha256": _sha(package / "case-plan.json"),
            "semantic_cases_sha256": _sha(package / "proposals/cases.json"),
            "cases": entries,
            "comparisons": [{"comparison_id": "distance_500ft",
                             "case_ids": comparisons[0]["case_ids"],
                             "audit_script": "comparison_audit.py",
                             "source_review": "pending"}],
            "canonical_execution_manifest": "not_yet_created"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite selected delivery draft")
    args.output.write_text(json.dumps(build(args.package), indent=2) + "\n")


if __name__ == "__main__":
    main()
