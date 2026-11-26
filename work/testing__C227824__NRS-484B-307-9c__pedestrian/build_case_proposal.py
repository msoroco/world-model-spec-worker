"""Emit exact four-case signal and pedestrian-entry proposal."""
from __future__ import annotations

import json
from pathlib import Path

from build_bundles import recording_description
from delivery_audit import ASSIGNMENT

HERE = Path(__file__).resolve().parent
VARIABLES = ("movement", "other_device_display")


def main():
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    rows = []
    for source in plan["cases"]:
        suffix = source["case_id"].removeprefix(ASSIGNMENT + "__")
        values = {name: {"kind": "world_setup", "unit": "categorical", "value": source[name]}
                  for name in VARIABLES}
        rows.append({"case_id": source["case_id"], "target_law_id": plan["law_id"],
                     "target_type": "boundary_probe",
                     "paired_probe_id": "signal_entry_controlled_cases",
                     "probe": {"primary_variable": "other_device_display" if suffix == "enter_walk_display" else "movement",
                               "target_value_or_branch": suffix,
                               "comparison_or_standard": "Original source observations; no legal verdict"},
                     "deliberate_differences": list(VARIABLES),
                     "variable_assignments": values,
                     "recording_description": recording_description(),
                     "rationale": "Source-gated concurrent red/turn-arrow signal, other-device inventory, facing and highway body entry.",
                     "unresolved_judgment_calls": [{"phrase": "unless permitted to proceed by another device as provided in NRS 484B.283",
                                                    "note": "WALK display is observed but permission under NRS 484B.283 requires independent source review."}]})
    baseline = dict(rows[0])
    baseline["case_id"] = ASSIGNMENT + "__baseline"
    baseline["target_law_id"] = None
    baseline["target_type"] = "baseline"
    baseline.pop("paired_probe_id", None)
    baseline.pop("probe", None)
    baseline.pop("deliberate_differences", None)
    baseline["rationale"] = "Shared four-case signal/highway observation definition; no separate recording."
    comparisons = []
    for source in plan["comparisons"]:
        variable = "other_device_display" if source["comparison_id"] == "other_device_display_entry" else "movement"
        comparisons.append({"comparison_id": source["comparison_id"],
                            "case_ids": source["case_ids"],
                            "fixed_conditions": [source["fixed_conditions"]],
                            "deliberate_differences": [variable]})
    sweep = {"status": "incomplete", "sweep_id": ASSIGNMENT + "__other_device_permission",
             "target_law_id": plan["law_id"],
             "judgment_refs": [{"phrase": "unless permitted to proceed by another device as provided in NRS 484B.283",
                                "note": "WALK display is observed but permission under NRS 484B.283 requires independent source review."}],
             "missing_inputs": ["reviewed original signal and other-device assets",
                                "source-supported feasible physical display/timing controls and NRS 484B.283 permission authority"],
             "rationale": "Frozen sources contain no exact C227824 judgment range or original device permission evidence."}
    proposal = {"status": "draft", "cell_id": plan["cell_id"], "actor": plan["actor"],
                "source_assignment": "inputs/" + ASSIGNMENT + "/assignment.json",
                "source_law_text": plan["law_text"], "cases": [baseline] + rows,
                "comparisons": comparisons, "sweep_specs": [sweep],
                "sweeps_expanded": False}
    output = HERE / "proposals/cases.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
