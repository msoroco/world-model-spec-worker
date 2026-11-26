"""Preview bounded controller sampling without claiming legal or site authority.

The preview is expanded by the pinned runtime in scratch. It is not a selected
proposal until every expanded case has a bundle and positive/negative proofs.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from reviewed_scene import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
AXES = {
    "impediment": ("slow_middle_follower", "ego_speed_mps", "ego_speed_mps", (4.0, 5.0, 6.0)),
    "passing_necessity": ("slow_middle_passing", "slower_speed_mps", "slower_vehicle_speed_mps", (2.0, 3.0, 4.0)),
}


def preview() -> dict:
    proposal = json.loads((ROOT / "proposals/cases.json").read_text(encoding="utf-8"))
    proposal["cases"] = [case for case in proposal["cases"]
                         if case.get("target_type") != "judgment_sweep"]
    cases = {case["case_id"]: case for case in proposal["cases"]}
    grids = []
    for old in proposal["sweep_specs"]:
        name = old["sweep_id"].removeprefix(ASSIGNMENT + "__")
        if name not in AXES:
            raise ValueError("unexpected judgment sweep")
        anchor, variable, observable, values = AXES[name]
        source = cases[ASSIGNMENT + "__" + anchor]
        assignments = deepcopy(source["variable_assignments"])
        assignments[variable] = {
            "kind": "controller", "unit": "m/s", "value": values[0],
            "note": "Authored speed request; retain all original measured speeds separately",
        }
        description = deepcopy(source["recording_description"])
        description["channels"].append({
            "name": observable, "unit": "m/s",
            "method": "20 Hz original Native actor speed readback",
            "reference_frame": "same original Native frame and simulation time",
            "sampling_rate_hz": 20,
            "time_window": "45-second original episode",
            "uncertainty": "Controller request is not guaranteed realized speed or legal outcome",
        })
        grids.append({
            "sweep_id": old["sweep_id"], "target_law_id": old["target_law_id"],
            "judgment_refs": deepcopy(old["judgment_refs"]), "status": "complete",
            "mode": "one_dimensional", "landmarks": [],
            "rationale": "Bounded physical speed sampling; impediment and passing necessity remain legal review questions.",
            "recording_description": description,
            "variable_assignments": assignments,
            "axes": [{
                "variable": variable, "observable": observable, "unit": "m/s",
                "min": values[0], "max": values[-1], "spacing": values[1] - values[0],
                "measurement": {
                    "method": "original 20 Hz Native actor speed readback, with full trace retained",
                    "time_window": "entire original 45-second episode", "statistic": "mean",
                },
                "range_rationale": "Authored low-speed controller requests for the 45-second route; not a training bound, legal cutoff, or claimed physical outcome.",
                "spacing_rationale": "Three distinguishable controller requests; realized spacing needs original trace review.",
                "feasibility_evidence": "source_gated_sweeps.py and its CPU fake-adapter tests exercise the requested controller values; original highway and physical feasibility remain unverified.",
            }],
        })
    proposal["sweep_specs"] = grids
    proposal["sweeps_expanded"] = False
    proposal["engineering_preview_only"] = True
    return proposal


def main() -> None:
    result = preview()
    path = ROOT / "engineering-sweep-preview.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "engineering_preview_only", "sweep_ids":
                      [spec["sweep_id"] for spec in result["sweep_specs"]]}))


if __name__ == "__main__":
    main()
