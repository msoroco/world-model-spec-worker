"""Finish the interrupted selected shuttle direct Core diagnostic."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.package_compatibility import CHECKS
from worker_exchange.measurement_contract import verify_report
from worker_exchange.media import verify_receipt
from worker_exchange.runtime_cli import execution_env
from batch_pipeline.carla import validate_attempt
from traffic_spec_adapter.validate import validate_output

SCRATCH = REPO / ".runtime-work/owner150142/shuttle-below-direct-current"
CASE = HERE.name + "__shuttle_bus_below"
CONTRACT = HERE / "selected-primary/shuttle_bus_below/selected-measurement-contracts/shuttle_bus_below.json"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text())


def run():
    configured = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not configured or not Path(configured).resolve().is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    manifest = HERE / "execution-manifest.json"
    entry = next(item for item in read(manifest)["cases"] if item["case_id"] == CASE)
    positive = SCRATCH / "positive"
    fixture = SCRATCH / "fixture"
    negative = SCRATCH / "negative"
    selection = read(positive / "candidate-selection.json")
    assert selection["case_id"] == CASE and selection["candidate_id"] == "primary"
    assert selection["manifest_sha256"] == sha(manifest)
    assert selection["construction_sha256"] == entry["construction_sha256"]
    for name in ("trace.jsonl", "native-raw-actors.jsonl", "native-passenger-actors.jsonl",
                 "video_frames.jsonl", "overview.mkv", "approach.mkv",
                 "reference_corner.mkv", "driver_reference.mkv"):
        assert sha(fixture / name) == sha(positive / name), name
    result = read(positive / "result.json")
    assert result["case_id"] == CASE
    assert len((positive / "trace.jsonl").read_text().splitlines()) == 36120
    mapping_sha = sha(positive / "video_frames.jsonl")
    source_audits = {}
    for index, reference in enumerate(result["video_references"]):
        source_audits[reference] = verify_receipt(
            positive / reference, read(positive / f"source-{index}.json"),
            36120, mapping_sha256=mapping_sha)
    proposal_case = next(item for item in read(HERE / "proposals/cases.json")["cases"]
                         if item["case_id"] == CASE)
    config = read(positive / "config.json")
    validate_attempt(positive,
                     {"case": proposal_case, "cell": {"cell_id": config["cell_id"]},
                      "actor": config["actor"]},
                     read(positive / "construction.json"),
                     {"recorded_exit_code": 0}, {}, source_audits=source_audits)
    final = read(positive / "final-decode.json")
    assert final["passed"] and final["frames"] == 36120
    assert final["video_sha256"] == sha(positive / "event_review.webm")
    for name in ("trace.json", "adapter_report.json", "atom_contract.json"):
        assert (positive / "converted" / name).is_file()
    validate_output(positive / "converted",
                    REPO / ".runtime-work/c111250-current-decoder/.lake/build/bin/adapterCheck")
    contract = read(CONTRACT)
    measurements = verify_report(contract, read(positive / "analysis-report.json"), fixture)
    removed = contract["negative"]["remove"][0]
    assert removed == "native-passenger-actors.jsonl"
    for source in fixture.iterdir():
        target = negative / source.name
        if source.name == removed or target.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    if (negative / removed).exists():
        assert sha(negative / removed) == sha(fixture / removed)
        (negative / removed).unlink()
    assert not (negative / removed).exists()
    failure = subprocess.run(
        [sys.executable, str(negative / "finalize_selected.py"),
         "--attempt", str(negative), "--output", str(negative / "analysis-report.json")],
        cwd=negative, env=execution_env(), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=300)
    expected = contract["negative"]["error_contains"]
    negative_log = SCRATCH / "negative-analysis.log"
    negative_log.write_text(failure.stdout.rstrip() + "\n")
    assert failure.returncode != 0 and expected in failure.stdout
    return {
        "format": "c150142-direct-long-compatibility-core-v1",
        "passed": True, "case_id": CASE, "candidate_id": "primary", "frames": 36120,
        "manifest_sha256": sha(manifest),
        "construction_sha256": entry["construction_sha256"],
        "core_checks": sorted(CHECKS),
        "positive_analysis_sha256": sha(positive / "finalize_selected.py"),
        "measurement_keys": sorted(measurements),
        "negative_removed": removed,
        "negative_error_contains": expected,
        "negative_log_sha256": sha(negative_log),
        "scope": "direct synthetic compatibility core; no pinned recipe receipt",
        "original_native_observed": False,
        "physical_acceptance_claimed": False,
        "legal_acceptance_claimed": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
