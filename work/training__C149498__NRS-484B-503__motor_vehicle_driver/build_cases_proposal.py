"""Draft canonical six-case proposal without a physical or legal verdict."""

import json
from pathlib import Path

from build_selected import AID, CASES, PREFIX, config, description

HERE = Path(__file__).resolve().parent


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    by_id = {case["case_id"]: case for case in plan["cases"]}
    entries = []
    for slug in CASES:
        cid = PREFIX + slug
        scene = by_id[cid]
        cfg = config(slug)
        entries.append({"case_id": cid, "target_law_id": "NRS-484B-503",
            "target_type": "boundary_probe",
            "probe": {"primary_variable": scene["comparison_variable"],
                      "comparison_or_standard": "Source-measured passenger curb episode with no invented legal cutoff",
                      "target_value_or_branch": slug},
            "paired_probe_id": "C149498-passenger-curb-branches",
            "deliberate_differences": [scene["comparison_variable"]],
            "rationale": "Authored sign, action and transfer requests need original Native and independent review.",
            "recording_description": description(),
            "unresolved_judgment_calls": ["zone regulatory authority", "actual passenger loading or unloading",
                                          "expeditiousness", "legal effect of measured duration"],
            "variable_assignments": {
                "actual_passenger_loading": {"kind": "controller", "unit": "category",
                    "value": "requested" if CASES[slug] else "not_requested"},
                "signed_effective_hours": {"kind": "civil_time", "unit": "category",
                    "value": "outside" if slug.startswith("outside_hours") else "inside"},
                "action_and_measured_duration": {"kind": "controller", "unit": "category",
                    "value": cfg["action_request"]}}})
    value = {"actor": "motor_vehicle_driver", "cell_id": "C149498",
        "status": "draft", "sweeps_expanded": True,
        "cases": entries, "sweep_specs": []}
    path = HERE / "proposals/cases.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return {"cases": len(entries), "proposal": str(path)}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
