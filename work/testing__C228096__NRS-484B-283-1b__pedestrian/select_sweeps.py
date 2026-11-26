"""Expand the tested engineering grids into exact source-gated case intents."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_sweep_preview import preview
from delivery_audit import ASSIGNMENT


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work" / "c228096-owner"


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="select-sweeps-", dir=SCRATCH) as temp:
        folder = Path(temp)
        proposal_path, templates_path, expanded_path = (
            folder / name for name in ("proposal.json", "templates.json", "expanded.json"))
        write(proposal_path, preview())
        write(templates_path, [json.loads((ROOT / "proposals/template.json").read_text())])
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(folder),
                   TMPDIR=str(folder), PYTHONDONTWRITEBYTECODE="1")
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                   "expand", "--proposal", str(proposal_path),
                   "--templates", str(templates_path),
                   "--bindings", str(ROOT / "proposals/bindings.json"),
                   "--output", str(expanded_path)]
        subprocess.run(command, cwd=REPO, env=env, check=True, capture_output=True, text=True)
        expanded = json.loads(expanded_path.read_text())
    expanded.pop("engineering_preview_only", None)
    extras = [case for case in expanded["cases"] if case.get("sweep_id")]
    if len(extras) != 6:
        raise ValueError("exact six-case expansion required")
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    plan["cases"] = [case for case in plan["cases"] if not case.get("sweep_id")]
    plan["comparisons"] = [comparison for comparison in plan["comparisons"]
                           if not comparison["comparison_id"].startswith("sweep_")]
    for extra in extras:
        point = extra["sweep_point"]
        plan["cases"].append({"case_id": extra["case_id"],
                              "target_law_id": plan["law_id"],
                              "branch": "bounded source-gated judgment physical sampling",
                              "action": "walk", "route_kind": "path",
                              "vehicle_gap_probe": "close",
                              "sweep_id": extra["sweep_id"], "sweep_point": point,
                              "gap_ids": ["no-accepted-recording"],
                              "construction": "curb_entry.construct with selected timed departure or vehicle station",
                              "measurement": "original 20 Hz motion, actual departure and vehicle separation at road entry",
                              "legal_judgment": "suddenness, yield opportunity and exceptions unresolved",
                              "physical_risk": "actual Native control realization and four-camera visibility require original review"})
    for sweep in expanded["sweep_specs"]:
        ids = sweep["selection_order"]
        label = sweep["sweep_id"].rsplit("__", 1)[-1]
        for index, (left, right) in enumerate(zip(ids, ids[1:])):
            cid = "sweep_" + label + "_" + str(index)
            plan["comparisons"].append({"comparison_id": cid,
                                        "case_ids": [left, right],
                                        "fixed_conditions": "same original site, curb, driver, vehicle path, gait, cameras and duration except the selected controller station",
                                        "deliberate_differences": [sweep["axes"][0]["variable"]]})
            expanded["comparisons"].append({"comparison_id": cid,
                                            "case_ids": [left, right],
                                            "fixed_conditions": ["same original site, curb, driver, vehicle path, gait, cameras and duration except the selected controller station"],
                                            "deliberate_differences": [sweep["axes"][0]["variable"]]})
    plan["requirement_dispositions"][0]["case_ids"] = [c["case_id"] for c in plan["cases"]]
    write(plan_path, plan)
    write(ROOT / "proposals/cases.json", expanded)
    print(f"Selected {len(plan['cases'])} exact cases and {len(plan['comparisons'])} comparisons")


if __name__ == "__main__":
    main()
