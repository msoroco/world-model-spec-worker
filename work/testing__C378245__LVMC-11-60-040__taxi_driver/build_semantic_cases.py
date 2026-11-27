"""Draft the six exact taxi branches for later canonical stage validation."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build() -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    if plan["cell_id"] != "C378245" or plan["law_id"] != "LVMC-11-60-040":
        raise ValueError("taxi semantic draft changed the frozen cell/law")
    target_types = {
        "designated_stand_park": "compliant_attempt",
        "outside_stand_park": "violating_attempt",
        "outside_stand_stand": "violating_attempt",
        "outside_stand_load": "boundary_probe",
        "outside_stand_unload": "boundary_probe",
        "outside_stand_idle_stop": "boundary_probe",
    }
    pair_ids = {
        "designated_stand_park": "stand_designation",
        "outside_stand_park": "stand_designation",
        "outside_stand_stand": "park_versus_stand",
        "outside_stand_load": "passenger_exception",
        "outside_stand_unload": "passenger_exception",
        "outside_stand_idle_stop": "passenger_exception",
    }
    cases = []
    for planned in plan["cases"]:
        suffix = planned["case_id"].split("__")[-1]
        variables = {name: {"kind": "world_setup" if name == "location_request" else "controller",
                            "value": planned[name]}
                     for name in ("location_request", "halt_activity_request",
                                  "passenger_exchange_request")}
        cases.append({
            "case_id": planned["case_id"], "target_law_id": plan["law_id"],
            "target_type": target_types[suffix], "paired_probe_id": pair_ids[suffix],
            "deliberate_differences": ["location_request" if suffix in
                                      ("designated_stand_park", "outside_stand_park")
                                      else "passenger_exchange_request" if suffix.startswith("outside_stand_l")
                                      or suffix == "outside_stand_idle_stop" else "halt_activity_request"],
            "probe": {"primary_variable": "location_request" if suffix in
                      ("designated_stand_park", "outside_stand_park")
                      else "passenger_exchange_request" if suffix.startswith("outside_stand_l")
                      or suffix == "outside_stand_idle_stop" else "halt_activity_request",
                      "comparison_or_standard": "designated taxi stand and actual passenger-exchange exception",
                      "target_value_or_branch": planned["target"]},
            "rationale": "Controlled requested physical branch; original stand, taxi, activity and exception facts require source review.",
            "variable_assignments": variables,
            "unresolved_judgment_calls": [],
            "recording_description": planned["recording_description"],
        })
    return {"format": "worker-taxi-semantic-draft", "status": "draft",
            "cell_id": plan["cell_id"], "actor": plan["actor"],
            "cases": cases, "sweep_specs": [],
            "canonical_stage_validation": "pending template, judgment and binding proposals"}


if __name__ == "__main__":
    output = ROOT / "proposals/cases.draft.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n")
    print(output)
