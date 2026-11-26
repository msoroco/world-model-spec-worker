"""Select exact finite judgment probes after pinned expansion."""

import json
import hashlib
from pathlib import Path

from package_contract import ACTOR, CELL, LAW


HERE = Path(__file__).resolve().parent


def main():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    path = HERE / "case-plan.json"
    plan = json.loads(path.read_text())
    plan["cases"] = [c for c in plan["cases"] if not c.get("sweep_id")]
    plan["comparisons"] = [c for c in plan["comparisons"] if not c["comparison_id"].startswith("sweep_")]
    for case in proposal["cases"]:
        if not case.get("sweep_id"):
            continue
        point = case["sweep_point"]
        controller, target = next(iter(point.items()))
        plan["cases"].append({"actor": ACTOR, "cell_id": CELL, "target_law_id": LAW,
                              "case_id": case["case_id"], "variant": case["case_id"].rsplit("__", 1)[-1],
                              "sweep_id": case["sweep_id"], "sweep_point": point,
                              "planning_status": "source_gated_exact_target_unexecuted",
                              "warning_request": "human_warning", "release_request": "person_departed" if controller == "departure_onset_s" else "go_signal",
                              "ego_response_request": "proceed", "stopping_reference_distance_target": "51ft",
                              "recording_description": "Original 20 Hz person state and four synchronized camera frames",
                              "controller_request": {controller: target},
                              "legal_judgment": "child warning or locality judgment remains unresolved"})
    for spec in proposal["sweep_specs"]:
        label = spec["sweep_id"].rsplit("__", 1)[-1]
        axis = spec["axes"][0]["variable"]
        for i, (left, right) in enumerate(zip(spec["selection_order"], spec["selection_order"][1:])):
            cid = "sweep_" + label + "_" + str(i)
            comparison = {"comparison_id": cid, "case_ids": [left, right],
                          "fixed_conditions": ["same reviewed original school lane, vehicle, warning actor, cameras and duration except timing station"],
                          "deliberate_differences": [axis]}
            plan["comparisons"].append(comparison)
            proposal["comparisons"].append(comparison)
    for req in plan.get("requirement_dispositions", []):
        if isinstance(req.get("case_ids"), list):
            req["case_ids"] = [c["case_id"] for c in plan["cases"]]
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    (HERE / "proposals/cases.json").write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")
    index_path = HERE / "proposals/semantic-index.json"
    index = json.loads(index_path.read_text())
    index["stages"]["cases"]["sha256"] = hashlib.sha256((HERE / "proposals/cases.json").read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    print(f"Selected {len(plan['cases'])} cases and {len(plan['comparisons'])} comparisons")


if __name__ == "__main__":
    main()
