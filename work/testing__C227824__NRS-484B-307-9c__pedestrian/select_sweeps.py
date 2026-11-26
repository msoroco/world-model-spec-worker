"""Expand the tested physical grid with the pinned runtime and select its cases."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_sweep_preview import AXIS, OBSERVABLE, preview


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c227824-owner"


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="select-sweeps-", dir=SCRATCH) as name:
        scratch = Path(name)
        source, templates, expanded_path = (scratch / item for item in
                                            ("proposal.json", "templates.json", "expanded.json"))
        write(source, preview())
        write(templates, [json.loads((ROOT / "proposals/template.json").read_text())])
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch),
                   TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE="1")
        subprocess.run([str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                        "expand", "--proposal", str(source), "--templates", str(templates),
                        "--bindings", str(ROOT / "proposals/bindings.json"),
                        "--output", str(expanded_path)], cwd=REPO, env=env, check=True)
        expanded = json.loads(expanded_path.read_text())
    expanded.pop("engineering_preview_only", None)
    for case in expanded["cases"]:
        values = case["variable_assignments"]
        values.setdefault(AXIS, {"kind": "controller", "unit": "m/s", "value": None,
                                 "note": "inactive in the original categorical comparison"})
        values.setdefault(OBSERVABLE, {"kind": "subject_behavior", "unit": "m/s", "value": None})
    sweep = expanded["sweep_specs"][0]
    extras = [case for case in expanded["cases"] if case.get("sweep_id")]
    if len(extras) != 3 or len(sweep["selection_order"]) != 3:
        raise ValueError("three exact walking-speed stations required")
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["cases"] = [case for case in plan["cases"] if not case.get("sweep_id")]
    plan["comparisons"] = [c for c in plan["comparisons"]
                           if not c["comparison_id"].startswith("sweep_walk_speed_")]
    for extra in extras:
        plan["cases"].append({"case_id": extra["case_id"], "target_law_id": plan["law_id"],
                              "branch": "source-gated physical sampling of pedestrian approach under displayed other device",
                              "movement": "enter", "other_device_display": "walk",
                              "sweep_id": extra["sweep_id"], "sweep_point": extra["sweep_point"],
                              "gap_ids": ["no-accepted-recording"],
                              "construction": "ped_entry.construct with the selected original walking-speed controller request",
                              "measurement": "original 20 Hz pedestrian body velocity, entry and concurrent signal/device readbacks",
                              "legal_judgment": "other-device authority and permission under NRS 484B.283 unresolved",
                              "physical_risk": "original source, walker motion and four-camera coverage require local review"})
    ids = sweep["selection_order"]
    for index, (left, right) in enumerate(zip(ids, ids[1:])):
        comparison_id = "sweep_walk_speed_" + str(index)
        fixed = "same reviewed highway, pedestrian route, steady red/green turn arrow, other-device WALK display, cameras and duration"
        plan["comparisons"].append({"comparison_id": comparison_id, "case_ids": [left, right],
                                    "fixed_conditions": fixed, "deliberate_differences": [AXIS]})
        expanded["comparisons"].append({"comparison_id": comparison_id, "case_ids": [left, right],
                                        "fixed_conditions": [fixed], "deliberate_differences": [AXIS]})
    for disposition in plan["requirement_dispositions"]:
        if disposition["status"] == "selected_required":
            disposition["case_ids"] = [case["case_id"] for case in plan["cases"]]
    write(plan_path, plan)
    write(ROOT / "proposals/cases.json", expanded)
    print(f"Selected {len(plan['cases'])} exact cases and {len(plan['comparisons'])} comparisons")


if __name__ == "__main__":
    main()
