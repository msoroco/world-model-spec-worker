"""Exercise a selected long fallback against the full compact-source fixture.

This is selected synthetic Core diagnostic work. The pinned public recipe path
cannot materialize this fixture, so the proof is not an official receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNTIME_WORK = (REPO / ".runtime-work").resolve()
configured = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
if RUNTIME_WORK not in configured.parents:
    raise ValueError("Runtime output must be under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.common import digest
from worker_exchange.fixture_recipe import fixture_fingerprint
from worker_exchange.measurement_contract import verify_report
from worker_exchange.package_compatibility import _process_fixture, materialize_case
from worker_exchange.runtime_cli import execution_env

CASE = HERE.name + "__tour_bus_below"
MANIFEST = HERE / "execution-manifest.json"
CONTRACT = HERE / "selected-primary/tour_bus_below/selected-measurement-contracts/tour_bus_below.json"
PRIMARY_PROOF = HERE / "current-long-compact-materialized-proof.json"
INDEX = HERE / "current-long-complete-source-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(fixture: Path, output: Path, validator: Path, candidate: str) -> dict:
    if candidate not in {"fallback1", "fallback2", "fallback3"}:
        raise ValueError("Select one exact long fallback")
    fixture, output, validator = fixture.resolve(), output.resolve(), validator.resolve()
    if RUNTIME_WORK not in fixture.parents or RUNTIME_WORK not in output.parents or output.exists():
        raise ValueError("Use retained full fixture and fresh output under .runtime-work")
    if not validator.is_file() or not (fixture / "capture/evidence.jsonl").is_file():
        raise ValueError("Pinned validator or full synthetic source missing")
    index = json.loads(INDEX.read_text())
    primary = json.loads(PRIMARY_PROOF.read_text())
    if index["case_id"] != CASE or primary["case_id"] != CASE or not primary["passed"]:
        raise ValueError("Retained source proof binds another case")
    inventory = fixture_fingerprint(fixture)
    fixture_sha = digest(inventory)
    if fixture_sha != primary["fixture_sha256"]:
        raise ValueError("Retained full source differs from compact primary proof")
    output.mkdir(parents=True)
    source = {"fixture_sha256": fixture_sha, "fixture_manifest": inventory}
    positive = output / "positive"
    receipt = _process_fixture(MANIFEST, CASE, fixture, positive,
                               REPO / "runtime/library", validator, candidate, source)
    contract = json.loads(CONTRACT.read_text())
    measurements = verify_report(contract,
                                 json.loads((positive / "analysis-report.json").read_text()), fixture)
    negative = output / "negative"
    materialize_case(MANIFEST, CASE, negative, fixture, candidate)
    removed = contract["negative"]["remove"][0]
    (negative / removed).unlink()
    failed = subprocess.run(
        [sys.executable, str(negative / "finalize_selected.py"),
         "--attempt", str(negative), "--output", str(negative / "analysis-report.json")],
        cwd=negative, env=execution_env(), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=300)
    (output / "negative-analysis.log").write_text(failed.stdout.rstrip() + "\n")
    expected = contract["negative"]["error_contains"]
    if failed.returncode == 0 or expected not in failed.stdout:
        raise ValueError("Missing-source fallback negative did not reject " + removed)
    return {"format": "c150142-compact-full-long-fallback-core-v1", "passed": True,
            "case_id": CASE, "candidate_id": candidate,
            "source_index_sha256": sha(INDEX), "primary_proof_sha256": sha(PRIMARY_PROOF),
            "fixture_sha256": fixture_sha, "manifest_sha256": sha(MANIFEST),
            "construction_sha256": receipt["construction_sha256"],
            "core_checks": receipt["checks"], "measurement_keys": sorted(measurements),
            "negative_removed": removed, "negative_error_contains": expected,
            "negative_log_sha256": sha(output / "negative-analysis.log"),
            "official_fixture_recipe_compatibility_passed": False,
            "original_native_observed": False,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validator", required=True, type=Path)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.fixture, args.output, args.validator, args.candidate),
                     indent=2, sort_keys=True))
