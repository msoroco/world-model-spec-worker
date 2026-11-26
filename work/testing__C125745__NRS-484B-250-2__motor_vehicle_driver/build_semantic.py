"""Draft exact source-gated timing cases without a legal outcome."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    constructions = {entry["case_id"]: json.loads((ROOT / entry["construction"]).read_text())
                     for entry in manifest["cases"]}
    cases = []
    for planned in plan["cases"]:
        exact = planned["case_id"]
        target = planned["scenario_parameters"]["entry_time_difference_target_s"]
        cases.append({"case_id": exact, "target_law_id": "NRS-484B-250-2",
                      "target_type": "full_test",
                      "rationale": "Measure original footprint entry brackets at the frozen training-range target; accepted metadata lacks this measurement.",
                      "variable_assignments": {
                          "entry_time_difference_target_s": {
                              "kind": "controller", "value": target,
                              "note": "engineering target only; not a legal cutoff or measured timing"}},
                      "unresolved_judgment_calls": [
                          "Approximately same time requires source-grounded legal judgment",
                          "Official traffic-control-device status and priority remain unreviewed"],
                      "recording_description": constructions[exact]["recording_description"]})
    proposal = {"status": "draft", "semantic_status": "partial_original_source_review",
                "cell_id": "C125745", "actor": "motor_vehicle_driver",
                "cases": cases, "sweeps_expanded": False,
                "sweep_specs": [{"sweep_id": "approximately_same_time_original_entry",
                                 "target_law_id": "NRS-484B-250-2", "status": "incomplete",
                                 "rationale": "Frozen range probes are training targets, not a legal definition.",
                                 "missing_inputs": ["Original 900-frame footprints, intersection polygon and legal timing review"],
                                 "judgment_refs": []},
                                {"sweep_id": "official_device_and_priority",
                                 "target_law_id": "NRS-484B-250-2", "status": "incomplete",
                                 "rationale": "The stop-sign cell label does not establish official control or left/right right-of-way.",
                                 "missing_inputs": ["Reviewed device authority and highway approach source packets"],
                                 "judgment_refs": []}]}
    out = ROOT / "proposals/cases.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")
    print("drafted", len(cases), "source-gated cases")


if __name__ == "__main__":
    main()
