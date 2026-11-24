"""Worker proposal for validating a permission-only plain-rule case set.

This is a scoped draft for local review. The pinned semantic validator is unchanged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PAIRS = {
    "second_lane_green_indication": (("adjacent_dark_drive", "second_green_drive"),
                                     "second_lane_green_request"),
    "green_permission_without_motion": (("green_selected_drive", "green_selected_stand"),
                                        "bus_motion_request"),
}


def validate(template, proposal, plan, assignment):
    if (template.get("law_id") != assignment["law_id"] or
            template.get("actor") != assignment["actor"] or
            template.get("quote") != assignment["law"]["text"] or
            template.get("structure", {}).get("obligation", {}).get("type") != "permission"):
        raise ValueError("exact permission template/source binding required")
    if template["structure"].get("judgment_calls_needed") or template["structure"].get("numeric_conditions"):
        raise ValueError("permission-only plain-rule scope required")
    prefix = assignment["assignment_id"] + "__"
    proposed_ids = [case.get("case_id") for case in proposal["cases"]]
    if len(set(proposed_ids)) != len(proposed_ids) or proposed_ids.count(prefix + "baseline") != 1:
        raise ValueError("duplicate or missing permission baseline/case identity")
    cases = {case["case_id"]: case for case in proposal["cases"] if case["target_type"] != "baseline"}
    expected = {prefix + kind for pair, _ in PAIRS.values() for kind in pair}
    planned_ids = [case.get("case_id") for case in plan["cases"]]
    if len(planned_ids) != len(set(planned_ids)) or set(planned_ids) != expected:
        raise ValueError("permission plan case identity mismatch")
    if set(cases) != expected or any(c["target_law_id"] != assignment["law_id"] or
                                     c["target_type"] != "boundary_probe" for c in cases.values()):
        raise ValueError("permission boundary case identity/type mismatch")
    comparison_ids = [c.get("comparison_id") for c in plan["comparisons"]]
    if len(comparison_ids) != len(set(comparison_ids)):
        raise ValueError("duplicate permission comparison identity")
    comparisons = {c["comparison_id"]: c for c in plan["comparisons"]}
    if set(comparisons) != set(PAIRS):
        raise ValueError("permission comparisons incomplete")
    for pair_id, (kinds, changed) in PAIRS.items():
        ids = [prefix + kind for kind in kinds]
        comp = comparisons[pair_id]
        if comp["case_ids"] != ids or not comp.get("fixed_conditions") or not comp.get("deliberate_differences"):
            raise ValueError("permission comparison pair or controls missing")
        first, second = (cases[ident] for ident in ids)
        if first.get("paired_probe_id") != pair_id or second.get("paired_probe_id") != pair_id:
            raise ValueError("permission probe link missing")
        if any(case.get("probe", {}).get("primary_variable") != changed or
               [item.get("variable") for item in case.get("deliberate_differences", [])] != [changed]
               for case in (first, second)):
            raise ValueError("permission probe declaration differs from comparison")
        descriptions = {case["deliberate_differences"][0].get("description")
                        for case in (first, second)}
        if len(descriptions) != 1 or comp["deliberate_differences"] != list(descriptions):
            raise ValueError("permission comparison description differs from probes")
        a = {key: value["value"] for key, value in first["variable_assignments"].items()}
        b = {key: value["value"] for key, value in second["variable_assignments"].items()}
        if set(a) != set(b) or {key for key in a if a[key] != b[key]} != {changed}:
            raise ValueError("permission comparison changes an undeclared variable")
    if any(c.get("legal_judgment") != "unresolved" or c.get("physical_acceptance_claimed") is not False
           for c in plan["cases"]):
        raise ValueError("permission planning claims unreviewed outcome")
    return {"format": "worker-permission-semantic-proposal-proof", "assignment_id": assignment["assignment_id"],
            "pair_ids": sorted(PAIRS), "case_ids": sorted(expected), "legal_verdict_claimed": False,
            "scope": "Worker-only permission boundary proof; pinned semantic validator unchanged"}


def validate_package(root, assignment, *, index=None, manifest=None):
    """Bind the permission proof to sealed stages and current exact constructions."""
    root = Path(root).resolve()
    index = index or json.loads((root / "proposals/semantic-index.json").read_text())
    manifest = manifest or json.loads((root / "execution-manifest.json").read_text())
    if index.get("assignment_id") != assignment["assignment_id"] or manifest.get("assignment_id") != assignment["assignment_id"]:
        raise ValueError("permission package assignment differs")
    stages = {}
    for name, ref in index.get("stages", {}).items():
        if name == "judgment_observables":
            if ref != []:
                raise ValueError("permission package invents judgment observables")
            continue
        relative = Path(ref.get("path", "")) if isinstance(ref, dict) else Path("")
        if (not relative.parts or relative.is_absolute() or ".." in relative.parts or
                (root / relative).is_symlink() or not (root / relative).is_file()):
            raise ValueError("permission stage source missing or escapes")
        digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        if digest != ref.get("sha256"):
            raise ValueError("permission stage source hash differs")
        stages[name] = json.loads((root / relative).read_text())
    if not {"template", "cases"} <= set(stages):
        raise ValueError("permission template/cases stage missing")
    plan = json.loads((root / "case-plan.json").read_text())
    report = validate(stages["template"], stages["cases"], plan, assignment)
    expected = set(report["case_ids"])
    entries = manifest.get("cases", [])
    if len(entries) != len(expected) or {entry.get("case_id") for entry in entries} != expected:
        raise ValueError("permission manifest case set differs")
    proposals = {case["case_id"]: case for case in stages["cases"]["cases"]
                 if case["target_type"] != "baseline"}
    constructions = {}
    for entry in entries:
        relative = Path(entry.get("construction", ""))
        if relative.is_absolute() or ".." in relative.parts or not (root / relative).is_file():
            raise ValueError("permission construction missing or escapes")
        raw = (root / relative).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        construction = json.loads(raw)
        if (digest != entry.get("construction_sha256") or
                construction.get("case_id") != entry["case_id"] or
                construction.get("recording_description") != proposals[entry["case_id"]].get("recording_description")):
            raise ValueError("permission construction/proposal binding differs")
        constructions[entry["case_id"]] = digest
    return {**report, "semantic_index_sha256": hashlib.sha256(
                (root / "proposals/semantic-index.json").read_bytes()).hexdigest(),
            "construction_sha256": constructions,
            "pinned_semantic_validator_passed": False}


def main():
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    report = validate_package(ROOT, assignment)
    from permission_attempt_pair import prove
    attempt_report = prove(ROOT, assignment)
    report["source_bound_attempt_pair_sha256"] = hashlib.sha256(
        json.dumps(attempt_report, sort_keys=True).encode()).hexdigest()
    report["pinned_compliant_violating_pair_claimed"] = attempt_report["pinned_compliant_violating_pair_claimed"]
    report["source_sha256"] = hashlib.sha256((REPO / "inputs" / ROOT.name / "assignment.json").read_bytes()).hexdigest()
    (ROOT / "proposals/permission-semantic-proposal-proof.json").write_text(json.dumps(report, indent=2) + "\n")
    print("worker-only permission semantic package and construction binding passed; pinned runtime remains unchanged")


if __name__ == "__main__":
    main()
