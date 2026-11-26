"""Draft source-gated canonical cases without assigning legal outcomes."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ID = ROOT.name


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    constructions = {entry["case_id"]: json.loads((ROOT / entry["construction"]).read_text())
                     for entry in manifest["cases"]}
    cases = []
    for planned in plan["cases"]:
        exact = planned["case_id"]
        config = json.loads(next(item["content"] for item in constructions[exact]["files"]
                                 if item["path"] == "config.json"))
        variables = config["case"]["draft_variables"]
        cases.append({"case_id": exact, "target_law_id": "NRS-484B-600-1c",
                      "target_type": "full_test", "rationale": (
                          "Retained accepted original source candidate for the " +
                          exact.rsplit("__", 1)[-1] +
                          " comparison; diagnostic construction is an alternate preparation only."),
                      "variable_assignments": {key: {"kind": "world_setup" if key not in
                          ("rate_relation",) else "controller", "value": value,
                          "note": "requested engineering relation; original measurement and authority remain unresolved"}
                          for key, value in variables.items()},
                      "unresolved_judgment_calls": [
                          "Original highway and public-authority jurisdiction review",
                          "Actual speed, sign visibility and governed portion review"],
                      "recording_description": constructions[exact]["recording_description"]})
    proposal = {"status": "draft", "semantic_status": "source_gated",
                "cell_id": "C136559", "actor": "motor_vehicle_driver",
                "cases": cases, "sweeps_expanded": False,
                "sweep_specs": [
                    {"sweep_id": "original_posted_rate_boundary", "target_law_id": "NRS-484B-600-1c",
                     "status": "incomplete", "rationale": "Actual original speed must be compared at the strict boundary; authored settings are not witnesses.",
                     "missing_inputs": ["Original Native speed and posted-rate packets for below, equal and above"],
                     "judgment_refs": []},
                    {"sweep_id": "governing_public_authority_and_portion", "target_law_id": "NRS-484B-600-1c",
                     "status": "incomplete", "rationale": "Highway dedication, public access, public posting and covered direction need reviewed sources.",
                     "missing_inputs": ["Original public-authority order, route and sign sources"],
                     "judgment_refs": []},
                    {"sweep_id": "off_camera_sign_reading", "target_law_id": "NRS-484B-600-1c",
                     "status": "incomplete", "rationale": "An invisible sign does not itself establish the governing posted rate.",
                     "missing_inputs": ["Original off-camera reading or authority-order assumption source"],
                     "judgment_refs": []}]}
    out = ROOT / "proposals" / "cases.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")
    print("drafted", len(cases), "source-gated canonical cases")


if __name__ == "__main__":
    main()
