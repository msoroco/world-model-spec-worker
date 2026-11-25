"""Run eight saved-only source and measurement diagnostics, never original claims."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from build_bundles import HERE, AID

REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work" / "c135087-selected-analysis-v1"
VIDEO_PROBE = REPO / ".runtime-work" / "c135087-fixture-video-probe"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_case(entry):
    cid = entry["case_id"]
    suffix = cid.removeprefix(AID + "__")
    case_root = SCRATCH / suffix
    if case_root.exists():
        raise ValueError("use a fresh diagnostic scratch revision")
    positive = case_root / "positive"
    positive.mkdir(parents=True)
    construction_path = HERE / entry["construction"]
    if sha(construction_path) != entry["construction_sha256"]:
        raise ValueError("selected construction hash changed")
    construction = json.loads(construction_path.read_text())
    for item in construction["files"]:
        target = positive / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"])
    source_dir = HERE / "diagnostics" / suffix
    recipe = json.loads((HERE / "diagnostics" / (suffix + "-recipe.json")).read_text())
    for item in recipe["sources"]:
        src = REPO / item["source"]
        if sha(src) != item["sha256"]:
            raise ValueError("diagnostic fixture source changed")
        shutil.copy2(src, positive / item["path"])
    attempt = json.loads((positive / "attempt-source.json").read_text())
    for name in VIEWS:
        source = VIDEO_PROBE / (name + ".mkv")
        if sha(source) != attempt["cameras"][name]["sha256"]:
            raise ValueError("diagnostic video source hash changed")
        shutil.copy2(source, positive / source.name)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(REPO / "runtime" / "scenario_pipeline") + ":" + str(positive),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / ".runtime-work" / "c135087-pipeline"))
    command = [sys.executable, str(positive / "analysis.py"), "--attempt", str(positive),
               "--output", str(positive / "analysis-report.json")]
    good = subprocess.run(command, text=True, capture_output=True, env=env, timeout=300)
    if good.returncode:
        raise ValueError("positive selected analysis failed: " + (good.stderr or good.stdout)[-1000:])
    report = json.loads((positive / "analysis-report.json").read_text())
    contract = json.loads((HERE / entry["measurement_contract"]).read_text())
    sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
    from worker_exchange.measurement_contract import verify_report
    verify_report(contract, report, positive)
    if report.get("diagnostic_fixture") is not True or report.get("physical_acceptance_claimed") or report.get("legal_verdict_claimed"):
        raise ValueError("diagnostic analysis made an unsupported claim")
    negative = case_root / "negative"
    negative.mkdir()
    shutil.copy2(positive / "config.json", negative / "config.json")
    shutil.copy2(positive / "attempt-source.json", negative / "attempt-source.json")
    shutil.copy2(positive / "analysis.py", negative / "analysis.py")
    negative_command = [sys.executable, str(negative / "analysis.py"), "--attempt", str(negative),
                        "--output", str(negative / "analysis-report.json")]
    bad = subprocess.run(negative_command, text=True, capture_output=True, env=env, timeout=30)
    expected = contract["negative"]["error_contains"]
    if bad.returncode == 0 or expected not in bad.stderr + bad.stdout:
        raise ValueError("missing original site source did not fail closed")
    log = HERE / f"selected-{suffix}-analysis.log"
    negative_log = HERE / f"selected-{suffix}-negative.log"
    log.write_text(good.stdout.rstrip() + "\n")
    negative_log.write_text((bad.stderr + bad.stdout).rstrip() + "\n")
    receipt = {"format": "c135087-synthetic-selected-analysis", "case_id": cid,
               "construction_sha256": entry["construction_sha256"],
               "fixture_recipe_sha256": sha(HERE / "diagnostics" / (suffix + "-recipe.json")),
               "diagnostic_fixture": True, "physical_acceptance_claimed": False,
               "legal_verdict_claimed": False, "positive_exit_code": 0,
               "report_sha256": sha(positive / "analysis-report.json"),
               "selected_measurements": sorted(report["measurements"]),
               "negative_exit_code": bad.returncode, "negative_expected_error": expected,
               "positive_log": log.name, "positive_log_sha256": sha(log),
               "negative_log": negative_log.name, "negative_log_sha256": sha(negative_log)}
    receipt_path = HERE / f"selected-{suffix}-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(suffix, "selected saved analysis and missing-site negative pass", flush=True)


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for entry in manifest["cases"]:
        run_case(entry)


if __name__ == "__main__":
    main()
