"""Emit exact five-case controlled comparison proposal for the assigned law."""
from __future__ import annotations

import json
from pathlib import Path

from build_bundles import recording_description
from delivery_audit import ASSIGNMENT


HERE = Path(__file__).resolve().parent
VARIABLES = ("action", "vehicle_gap", "route_kind")


def main():
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    rows = []
    for source in plan["cases"]:
        if source.get("sweep_id"):
            continue
        suffix = source["case_id"].removeprefix(ASSIGNMENT + "__")
        values = {name: {"kind": "world_setup", "unit": "categorical",
                         "value": source["vehicle_gap_probe" if name == "vehicle_gap" else name]}
                  for name in VARIABLES}
        rows.append({"case_id": source["case_id"],
                     "target_law_id": plan["law_id"],
                     "target_type": "boundary_probe",
                     "paired_probe_id": "curb_departure_controlled_cases",
                     "probe": {"primary_variable": "action" if suffix == "close_run_into_path" else "vehicle_gap" if suffix == "far_walk_into_path" else "route_kind",
                               "target_value_or_branch": source["case_id"].removeprefix(ASSIGNMENT + "__"),
                               "comparison_or_standard": "Original source observations; no legal verdict"},
                     "deliberate_differences": ["action", "vehicle_gap", "route_kind"],
                     "variable_assignments": values,
                     "recording_description": recording_description(),
                     "rationale": "Source-gated curb, path, vehicle and driver observation; physical and legal findings require original review.",
                     "unresolved_judgment_calls": [
                         {"phrase": "suddenly leave a curb or other place of safety",
                          "note": "No legal departure-time or gait cutoff is asserted."},
                         {"phrase": "so close that it is impossible for the driver to yield",
                          "note": "Observed separation and speed do not establish impossibility."}]})
    baseline = dict(rows[0])
    baseline["case_id"] = ASSIGNMENT + "__baseline"
    baseline["target_law_id"] = None
    baseline["target_type"] = "baseline"
    baseline.pop("paired_probe_id", None)
    baseline.pop("probe", None)
    baseline.pop("deliberate_differences", None)
    baseline["rationale"] = "Shared five-case source observation definition; no separate recording."
    comparisons = []
    for source in plan["comparisons"]:
        if source["comparison_id"].startswith("sweep_"):
            continue
        comparisons.append({"comparison_id": source["comparison_id"],
                            "case_ids": source["case_ids"],
                            "fixed_conditions": [source["fixed_conditions"]],
                            "deliberate_differences": ["action" if source["comparison_id"] == "walk_vs_run" else "vehicle_gap" if source["comparison_id"] == "close_vs_far" else "route_kind"]})
    sweep_specs = []
    for suffix, phrase, note in (
        ("sudden_departure", "suddenly leave a curb or other place of safety",
         "Original departure timing, curb and path authority require independent review; gait alone is no legal cutoff."),
        ("yield_impossibility", "so close that it is impossible for the driver to yield",
         "Original vehicle motion, driver opportunity and path geometry require independent review; proximity alone is no legal cutoff."),
    ):
        sweep_specs.append({"status": "incomplete", "sweep_id": ASSIGNMENT + "__" + suffix,
                            "target_law_id": plan["law_id"],
                            "judgment_refs": [{"phrase": phrase, "note": note}],
                            "missing_inputs": ["reviewed original site, curb/path geometry and Native actor packet",
                                               "source-supported feasible physical control range and spacing"],
                            "rationale": "Frozen sources contain no exact C228096 judgment range or legal numeric cutoff."})
    proposal = {"status": "draft", "cell_id": plan["cell_id"],
                "actor": plan["actor"], "source_assignment":
                "inputs/" + ASSIGNMENT + "/assignment.json",
                "source_law_text": plan["law_text"],
                "cases": [baseline] + rows, "comparisons": comparisons,
                "sweep_specs": sweep_specs, "sweeps_expanded": False}
    output = HERE / "proposals/cases.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")


if __name__ == "__main__":
    main()
