"""Select a finite, source-gated walking-speed grid with the pinned expander.

The controller setpoints are engineering probes, never legal permission bounds.
Original device authority and physical realization remain separate reviews.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c227824-8b-sweep"
AXIS = "walk_speed_target_mps"
OBSERVABLE = "original_pedestrian_speed_mps"


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    proposal = json.loads((ROOT / "proposals/cases.json").read_text())
    proposal["cases"] = [c for c in proposal["cases"] if not c.get("sweep_id")]
    proposal["comparisons"] = [c for c in proposal.get("comparisons", [])
                               if not c["comparison_id"].startswith("sweep_walk_speed_")]
    reference = next(c for c in proposal["cases"] if c["case_id"].endswith("__red_walk_entry"))
    previous = proposal["sweep_specs"][0]
    values = deepcopy(reference["variable_assignments"])
    values[AXIS] = {"kind": "controller", "unit": "m/s", "value": 0.8,
                    "note": "Requested walker speed; original body velocity measured separately"}
    values[OBSERVABLE] = {"kind": "subject_behavior", "unit": "m/s", "value": None}
    proposal["sweep_specs"] = [{
        "status": "complete", "sweep_id": ROOT.name + "__other_device_permission",
        "target_law_id": previous["target_law_id"],
        "judgment_refs": deepcopy(previous["judgment_refs"]),
        "mode": "one_dimensional", "landmarks": [],
        "rationale": "Sample finite walker control requests with the other device displaying WALK; official authority and NRS 484B.283 permission remain unresolved.",
        "recording_description": deepcopy(reference["recording_description"]),
        "variable_assignments": values,
        "axes": [{
            "variable": AXIS, "observable": "original_pedestrian_speed_mps", "unit": "m/s",
            "min": 0.8, "max": 1.6, "spacing": 0.4,
            "measurement": {"method": "original 20 Hz walker body displacement after startup, retaining original frame samples",
                            "time_window": "original seconds 6 through 12, excluding startup transient",
                            "statistic": "mean"},
            "range_rationale": "Three source-gated pedestrian control requests fit the existing 12-second crossing episode; these values are not permission thresholds.",
            "spacing_rationale": "Separated control requests sample physical behavior while holding red head, WALK display, route and camera plan fixed.",
            "feasibility_evidence": "walker_control.request accepts 0.8, 1.2 and 1.6 m/s and applies a CARLA WalkerControl; actual movement requires original Native readback."
        }]
    }]
    proposal["sweeps_expanded"] = False
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="expand-", dir=SCRATCH) as name:
        scratch = Path(name)
        source, templates, expanded_path = (scratch / n for n in
                                            ("proposal.json", "templates.json", "expanded.json"))
        write(source, proposal)
        write(templates, [json.loads((ROOT / "proposals/template.json").read_text())])
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch),
                   TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE="1")
        subprocess.run([str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                        "expand", "--proposal", str(source), "--templates", str(templates),
                        "--bindings", str(ROOT / "proposals/bindings.json"),
                        "--output", str(expanded_path)], cwd=REPO, env=env, check=True)
        expanded = json.loads(expanded_path.read_text())
    extras = [c for c in expanded["cases"] if c.get("sweep_id")]
    sweep = expanded["sweep_specs"][0]
    if len(extras) != 3 or len(sweep["selection_order"]) != 3:
        raise ValueError("three exact engineering sweep stations required")
    for case in expanded["cases"]:
        case["variable_assignments"].setdefault(
            AXIS, {"kind": "controller", "unit": "m/s", "value": None,
                   "note": "inactive in categorical red/device comparisons"})
        case["variable_assignments"].setdefault(
            OBSERVABLE, {"kind": "subject_behavior", "unit": "m/s", "value": None})
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["cases"] = [c for c in plan["cases"] if not c.get("sweep_id")]
    plan["comparisons"] = [c for c in plan["comparisons"]
                           if not c["comparison_id"].startswith("sweep_walk_speed_")]
    for case in extras:
        plan["cases"].append({
            "case_id": case["case_id"], "target_law_id": plan["law_id"],
            "target_type": "controlled_entry_probe", "gap_ids": ["red-entry-and-device-unverified"],
            "preparation_status": "source_bound_measurement_cpu_tested_construction_pending",
            "requested_behavior": "Request highway entry under separate WALK indication at an engineering walker speed",
            "other_device_indication": "walk", "entry_request": "entry",
            "walk_speed_target_mps": case["sweep_point"][AXIS],
            "sweep_id": case["sweep_id"], "sweep_point": case["sweep_point"],
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False,
            "physical_risk_assessment": deepcopy(plan["cases"][2]["physical_risk_assessment"]),
        })
    ids = sweep["selection_order"]
    for index, (left, right) in enumerate(zip(ids, ids[1:])):
        comparison_id = "sweep_walk_speed_" + str(index)
        fixed = "same red head, reviewed highway, pedestrian route, separate WALK display, cameras and duration"
        plan["comparisons"].append({"comparison_id": comparison_id,
                                    "case_ids": [left, right], "fixed_conditions": [fixed],
                                    "deliberate_differences": [AXIS],
                                    "status": "planned_cpu_measurement_only",
                                    "legal_judgment": "unresolved"})
        expanded["comparisons"].append({"comparison_id": comparison_id,
                                        "case_ids": [left, right], "fixed_conditions": [fixed],
                                        "deliberate_differences": [AXIS]})
    for disposition in plan["requirement_dispositions"]:
        if disposition["status"] == "selected_required":
            disposition["case_ids"] = [c["case_id"] for c in plan["cases"]]
    write(plan_path, plan)
    write(ROOT / "proposals/cases.json", expanded)
    print(f"Selected {len(plan['cases'])} exact cases and {len(plan['comparisons'])} comparisons")


if __name__ == "__main__":
    main()
