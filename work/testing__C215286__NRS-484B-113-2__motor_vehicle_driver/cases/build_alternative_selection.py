"""Stage exact full-branch plan and proposals without claiming delivery readiness."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT = ROOT.name
PAIRS = (
    ("intersection", "reverse_into_intersection", "reverse_stops_before_intersection",
     "reverse_intersection_entry_vs_stop", "intersection region"),
    ("street_corner", "reverse_around_street_corner", "reverse_stops_before_street_corner",
     "reverse_street_corner_entry_vs_stop", "street corner region"),
)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    proposal = json.loads((ROOT / "proposals/cases.json").read_text())
    manifest = json.loads((ROOT / "cases/alternative-offline-manifest.json").read_text())
    measurements = json.loads((ROOT / "cases/alternative-measurement-plan.json").read_text())
    bundles = {row["case_id"]: json.loads((ROOT / "cases" / row["construction"]).read_text())
               for row in manifest["cases"]}
    if len(plan["cases"]) != 2 or len(proposal["cases"]) != 3 or len(bundles) != 4:
        raise ValueError("Selected crosswalk baseline or staged alternatives changed")
    for alternative, entry, stop, comparison_id, region in PAIRS:
        ids = [ASSIGNMENT + "__" + suffix for suffix in (entry, stop)]
        for case_id, expected in zip(ids, (True, False)):
            bundle = bundles[case_id]
            target = "inside" if expected else "before"
            plan["cases"].append({
                "case_id": case_id,
                "target_law_id": "NRS-484B-113-2",
                "purpose": "Observe backing " + target + " the sourced " + region,
                "gap_ids": [alternative + "_geometry", "reverse_motion"],
                "physical_risk": "Reverse body or camera view may miss the authored " + region,
            })
            proposal["cases"].append({
                "case_id": case_id,
                "target_law_id": "NRS-484B-113-2",
                "target_type": "violating_attempt" if expected else "compliant_attempt",
                "rationale": "Measure original reverse complete-body entry and heading against a sourced "
                             + region + "; street status and legal result require independent review.",
                "variable_assignments": {
                    "reverse_route_target": {"kind": "controller", "value": target + "_" + alternative,
                                             "unit": "categorical"},
                    "region_body_overlap": {"kind": "subject_behavior", "value": None,
                                            "unit": "boolean"},
                    "native_site_status": {"kind": "world_setup", "value": "unverified",
                                           "unit": "categorical"},
                },
                "unresolved_judgment_calls": ["Actual Native site and camera source review pending"],
                "recording_description": bundle["recording_description"],
                "paired_probe_id": comparison_id,
                "deliberate_differences": ["reverse_route_target"],
                "probe": {"primary_variable": "reverse_route_target",
                          "comparison_or_standard": "paired original complete-body reverse region entry",
                          "target_value_or_branch": target + "_" + alternative},
            })
        plan["comparisons"].append({
            "comparison_id": comparison_id, "case_ids": ids,
            "fixed_conditions": ["same Native map, road, region, vehicle, start body, cameras and duration"],
            "deliberate_differences": ["reverse route enters region or stops before it"],
        })
    plan["requirement_dispositions"] = measurements["requirement_dispositions"]
    plan["selected_branch"] = (
        "Backing into an intersection, on or over a crosswalk, or around a street corner")
    plan["planning_status"] = "staged full-branch selection; delivery proofs and real-site review pending"
    plan["runtime_uncertainties"].append(
        "Intersection and corner sources are synthetic CPU diagnostics; original Native map/camera review pending.")
    ids = {row["case_id"] for row in plan["cases"]}
    proposed = {row["case_id"] for row in proposal["cases"] if row["target_type"] != "baseline"}
    if len(ids) != 6 or ids != proposed or len(plan["comparisons"]) != 3:
        raise ValueError("Staged full-branch case/proposal coverage differs")
    write(ROOT / "cases/alternative-selected-case-plan.json", plan)
    write(ROOT / "cases/alternative-selected-proposals.json", proposal)
    print("staged", len(ids), "exact cases and", len(plan["comparisons"]), "comparisons")


if __name__ == "__main__":
    build()
