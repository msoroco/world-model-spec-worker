"""Run pinned fixture/measurement contracts on four diagnostic sight packets."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output_root or not Path(output_root).resolve().is_relative_to(REPO / ".runtime-work"):
    raise ValueError("Set output root under .runtime-work before runtime imports")
sys.path.insert(0, str(REPO / "runtime"))
sys.path.insert(0, str(HERE))

from scenario_pipeline.worker_exchange.fixture_recipe import materialize
from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report
from scenario_pipeline.worker_exchange.native_output import validate_result
from scenario_pipeline.worker_exchange.runtime_cli import execution_env, materialize as materialize_bundle
from selected_analysis import measure_original_sight


def run() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    contract = json.loads((HERE / "selected-measurement-contract.draft.json").read_text())
    rows = {}
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(plan["assignment_id"] + "__")
        selected = validate(contract, plan["requirement_dispositions"],
                            (HERE / "selected_analysis.py").read_text(), case_id)
        recipe = HERE / "fixtures" / suffix / "fixture-recipe.json"
        with tempfile.TemporaryDirectory(dir=root, prefix="c129731-fixture-") as temporary:
            fixture = Path(temporary) / "positive"
            receipt = materialize(REPO, recipe, fixture)
            attempt = Path(temporary) / "attempt"
            materialize_bundle(HERE / "execution-manifest.draft.json", case_id, attempt)
            for source in fixture.iterdir():
                shutil.copy2(source, attempt / source.name)
            completed = subprocess.run(
                [sys.executable, str(attempt / "analysis.py"), "--attempt", str(attempt),
                 "--output", str(attempt / "analysis-report.json")],
                cwd=attempt, env=execution_env(), capture_output=True, text=True, timeout=60)
            if completed.returncode:
                raise ValueError("Source-shaped selected analysis failed: " + completed.stdout + completed.stderr)
            report = json.loads((attempt / "analysis-report.json").read_text())
            result = validate_result(json.loads((attempt / "result.json").read_text()))
            if result["maneuver_completed"] or not result["diagnostic_fixture"]:
                raise ValueError("Diagnostic attempt claimed original physical completion")
            measurements = verify_report(contract, report, fixture)
            if len(selected) != 6 or len(measurements) != 6 or "diagnostic" not in report["scope"]:
                raise ValueError("Incomplete diagnostic measurement proof")
            negative = Path(temporary) / "negative"
            materialize_bundle(HERE / "execution-manifest.draft.json", case_id, negative)
            for source in fixture.iterdir():
                shutil.copy2(source, negative / source.name)
            removed = contract["negative"]["remove"][0]
            (negative / removed).unlink()
            failure = subprocess.run(
                [sys.executable, str(negative / "analysis.py"), "--attempt", str(negative),
                 "--output", str(negative / "analysis-report.json")],
                cwd=negative, env=execution_env(), capture_output=True, text=True, timeout=60)
            if (failure.returncode == 0 or
                    contract["negative"]["error_contains"] not in failure.stdout + failure.stderr):
                raise ValueError("Missing source negative unexpectedly passed")
            if suffix != "distance_reference":
                tampered = Path(temporary) / "tampered-probe"
                materialize_bundle(HERE / "execution-manifest.draft.json", case_id, tampered)
                for source in fixture.iterdir():
                    shutil.copy2(source, tampered / source.name)
                packet = json.loads((tampered / "approach_motion.json").read_text())
                packet["first_turn_distance_m"] += 1
                (tampered / "approach_motion.json").write_text(json.dumps(packet) + "\n")
                failure = subprocess.run(
                    [sys.executable, str(tampered / "analysis.py"), "--attempt", str(tampered),
                     "--output", str(tampered / "analysis-report.json")],
                    cwd=tampered, env=execution_env(), capture_output=True, text=True, timeout=60)
                if failure.returncode == 0 or "Original approach probe hash differs" not in failure.stdout + failure.stderr:
                    raise ValueError("Tampered approach probe unexpectedly passed")
        rows[suffix] = {"selected_requirements": len(selected),
                        "measurement_keys": sorted(measurements),
                        "fixture_sha256": receipt["fixture_sha256"],
                        "recipe_sha256": receipt["recipe_sha256"],
                        "negative_removed": removed,
                        "materialized_analysis_and_result": True,
                        "stale_approach_probe_rejected": suffix != "distance_reference",
                        "scope": "diagnostic software compatibility only"}
    return {"format": "c129731-source-shaped-fixture-proof-v1",
            "assignment_id": plan["assignment_id"], "cases": rows,
            "native_or_legal_acceptance": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
