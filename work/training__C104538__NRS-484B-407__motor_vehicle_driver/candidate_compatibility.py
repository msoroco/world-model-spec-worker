"""Run current compatibility with C104538's candidate-specific source recipe.

The frozen runtime CLI accepts one recipe per case. C104538's Native context
records candidate identity, so each fallback needs its own source recipe. This
worker-owned adapter uses the frozen compatibility stages and retains their
normal positive, removed-source negative, Core/Lean and media checks.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
sys.path.insert(1, str(ROOT / "runtime/pipeline/python"))
os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT",
                  str(ROOT / ".runtime-work/adapter/c104538-candidate"))
from worker_exchange import fixture_generator
from worker_exchange.candidate_constructions import select
from worker_exchange.common import read, sha, tree, within, write
from worker_exchange.fixture_recipe import materialize
from worker_exchange.measurement_contract import validate, verify_report
from worker_exchange.package_compatibility import (
    _process_fixture, materialize_case)
from worker_exchange.runtime_cli import execution_env


def run(manifest: Path, case: str, candidate: str, recipe: Path,
        output: Path, library: Path, validator: Path) -> dict:
    manifest, recipe, output = (path.resolve() for path in (manifest, recipe, output))
    if manifest != HERE / "execution-manifest.json" or candidate not in {
            "fallback1", "fallback2", "fallback3"}:
        raise ValueError("Select one current C104538 fallback")
    entry = next((item for item in read(manifest)["cases"]
                  if item["case_id"] == case), None)
    if entry is None or entry["kind"] != "delivery":
        raise ValueError("Select a C104538 delivery case")
    suffix = case.rsplit("__", 1)[-1]
    if recipe != HERE / f"update015-{suffix}-{candidate}-recipe.json":
        raise ValueError("Candidate-specific recipe differs")
    if ROOT / ".runtime-work" not in output.parents or output.exists():
        raise ValueError("Output must be new under ignored .runtime-work")
    _, selected, construction = select(manifest, case, candidate)
    contract_path = within(HERE, entry["measurement_contract"])
    contract = read(contract_path)
    analysis_code = next(item["content"] for item in construction["files"]
                         if item["path"] == entry["measurement_procedure"]["entrypoint"])
    validate(contract, read(HERE / "case-plan.json")["requirement_dispositions"],
             analysis_code, case)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix="candidate-fixture-") as temp:
        fixture = Path(temp) / "positive"
        source = materialize(ROOT, recipe, fixture)
        context = read(fixture / "native-construction-context.json")
        if context.get("case_id") != case or context.get("candidate_id") != candidate:
            raise ValueError("Candidate fixture Native context differs")
        receipt = _process_fixture(manifest, case, fixture, output,
                                   library, validator, candidate)
        measurements = verify_report(contract, read(output / "analysis-report.json"), fixture)
        negative = Path(temp) / "negative"
        materialize_case(manifest, case, negative, fixture, candidate)
        removed = contract["negative"]["remove"][0]
        if removed not in tree(fixture):
            raise ValueError("Negative source absent from positive fixture")
        within(negative, removed).unlink()
        analysis = within(negative, entry["measurement_procedure"]["entrypoint"])
        failed = subprocess.run([sys.executable, str(analysis), "--attempt", str(negative),
                                 "--output", str(negative / "analysis-report.json")],
                                cwd=negative, env=execution_env(), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=300)
        (output / "negative-analysis.log").write_text(failed.stdout)
        expected = contract["negative"]["error_contains"]
        if failed.returncode == 0 or expected not in failed.stdout:
            raise ValueError("Candidate missing-source negative did not reject")
    receipt.update(format="worker-package-compatibility",
                   fixture_generator_sha256=sha(Path(fixture_generator.__file__)),
                   checks=receipt["checks"] + ["selected_measurements", "negative_case_source"],
                   fixture_recipe_sha256=source["recipe_sha256"],
                   measurement_contract_sha256=sha(contract_path),
                   analysis_report_sha256=sha(output / "analysis-report.json"),
                   measurement_keys=sorted(measurements), measurement_examples=measurements,
                   negative_removed=removed, negative_error_contains=expected,
                   negative_log_sha256=sha(output / "negative-analysis.log"),
                   worker_candidate_recipe=recipe.relative_to(ROOT).as_posix(),
                   worker_candidate_recipe_adapter_sha256=sha(Path(__file__)))
    if receipt.get("candidate_id") != selected["id"]:
        raise ValueError("Compatibility receipt selects another fallback")
    write(output / "compatibility.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for flag in ("manifest", "recipe", "output", "library", "validator"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.case, args.candidate, args.recipe,
                         args.output, args.library, args.validator), indent=2))
