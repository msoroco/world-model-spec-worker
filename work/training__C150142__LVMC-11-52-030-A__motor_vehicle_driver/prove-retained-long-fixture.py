"""Run a selected long Core diagnostic on a staged synthetic source fixture.

The fixture and its complete Native-shaped source remain under .runtime-work.
This direct Core test is not a public fixture-recipe compatibility receipt.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = (REPO / ".runtime-work").resolve()
configured = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
if SCRATCH not in configured.parents:
    raise ValueError("Runtime output must be under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.common import digest, tree
from worker_exchange.fixture_recipe import fixture_fingerprint
from worker_exchange.measurement_contract import verify_report
from worker_exchange.package_compatibility import _process_fixture, materialize_case
from worker_exchange.runtime_cli import execution_env


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def run(case, candidate, attempt, fixture, output, validator):
    attempt, fixture, output, validator = map(
        lambda path: Path(path).resolve(), (attempt, fixture, output, validator))
    if any(SCRATCH not in path.parents for path in (attempt, fixture, output)):
        raise ValueError("Synthetic source and outputs must remain under .runtime-work")
    if output.exists() or not validator.is_file():
        raise ValueError("Use a fresh output and an existing current validator")
    case_id = HERE.name + "__" + case
    manifest = HERE / "execution-manifest.json"
    entry = next(item for item in json.loads(manifest.read_text())["cases"]
                 if item["case_id"] == case_id)
    selection = json.loads((attempt / "candidate-selection.json").read_text())
    if selection["case_id"] != case_id or selection["candidate_id"] != candidate:
        raise ValueError("Retained selection differs from exact case or candidate")
    frame_count = json.loads((attempt / "config.json").read_text())["capture_frames"]
    if frame_count not in (36120, 36121, 36122):
        raise ValueError("Selected source does not have the long frame schedule")
    source_inventory = tree(fixture)
    if not source_inventory or set(source_inventory) & {
            "result.json", "analysis-report.json", "compatibility.json"}:
        raise ValueError("Fixture contains no source or supplies a result")
    for name in source_inventory:
        if sha(fixture / name) != sha(attempt / name):
            raise ValueError("Staged source differs from retained attempt: " + name)
    if sum(1 for _ in (fixture / "trace.jsonl").open()) != frame_count:
        raise ValueError("Staged trace does not cover selected duration")
    if sum(1 for _ in (fixture / "video_frames.jsonl").open()) != frame_count:
        raise ValueError("Staged frame map does not cover selected duration")
    output.mkdir(parents=True)
    fingerprint = fixture_fingerprint(fixture)
    source = {"fixture_sha256": digest(fingerprint), "fixture_manifest": fingerprint}
    positive = output / "positive"
    receipt = _process_fixture(manifest, case_id, fixture, positive,
                               REPO / "runtime/library", validator, candidate, source)
    if receipt["construction_sha256"] != entry["construction_sha256"]:
        raise ValueError("Selected construction differs")
    contract_path = HERE / "selected-primary" / case / "selected-measurement-contracts" / (case + ".json")
    contract = json.loads(contract_path.read_text())
    measurements = verify_report(contract,
                                 json.loads((positive / "analysis-report.json").read_text()), fixture)
    negative = output / "negative"
    materialize_case(manifest, case_id, negative, fixture, candidate)
    removed = contract["negative"]["remove"][0]
    (negative / removed).unlink()
    failure = subprocess.run(
        [sys.executable, str(negative / "finalize_selected.py"), "--attempt", str(negative),
         "--output", str(negative / "analysis-report.json")],
        cwd=negative, env=execution_env(), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=300)
    log = output / "negative-analysis.log"
    log.write_text(failure.stdout.rstrip() + "\n")
    expected = contract["negative"]["error_contains"]
    if failure.returncode == 0 or expected not in failure.stdout:
        raise ValueError("Missing-source negative did not reject " + removed)
    return {
        "format": "c150142-retained-long-direct-core-v1", "passed": True,
        "case_id": case_id, "candidate_id": candidate, "frames": frame_count,
        "manifest_sha256": sha(manifest),
        "construction_sha256": receipt["construction_sha256"],
        "source_selection_manifest_sha256": selection["manifest_sha256"],
        "source_selection_construction_sha256": selection["construction_sha256"],
        "fixture_sha256": source["fixture_sha256"], "source_files": len(fingerprint),
        "core_checks": receipt["checks"], "measurement_keys": sorted(measurements),
        "negative_removed": removed, "negative_error_contains": expected,
        "negative_log_sha256": sha(log),
        "official_fixture_recipe_compatibility_passed": False,
        "original_native_observed": False,
        "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--validator", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.candidate, args.attempt, args.fixture,
                         args.output, args.validator), indent=2, sort_keys=True))
