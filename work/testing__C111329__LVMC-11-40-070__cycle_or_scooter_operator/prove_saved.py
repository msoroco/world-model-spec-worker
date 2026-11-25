"""Run selected saved-only processing against each exact diagnostic fixture."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "").find(".runtime-work/") >= 0:
    raise RuntimeError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before importing pipeline")

from worker_exchange.fixture_recipe import materialize as materialize_fixture
from worker_exchange.runtime_cli import materialize
from worker_exchange.saved_processing import copy_sources

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c111329-saved-selected"
LIBRARY = REPO / ".runtime-work/c111329-validator/library"
VALIDATOR = REPO / ".runtime-work/c111329-validator/.lake/build/bin/adapterCheck"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    if not VALIDATOR.is_file():
        raise ValueError("assignment validator unavailable")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        work = SCRATCH / suffix
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        attempt, fixture, versions = (work / part for part in ("attempt", "fixture", "versions"))
        materialize(MANIFEST, case_id, attempt)
        # Primary diagnostic processing may omit candidate selection. This avoids
        # a manifest hash cycle while post_capture receipts are being bound.
        (attempt / "candidate-selection.json").unlink()
        materialize_fixture(REPO, REPO / entry["fixture_recipe"], fixture)
        copy_sources(fixture, attempt)
        command = [sys.executable, "runtime.py", "process-saved", "--manifest",
                   str(MANIFEST.relative_to(REPO)), "--case", case_id, "--attempt",
                   str(attempt.relative_to(REPO)), "--output", str(versions.relative_to(REPO)),
                   "--library", str(LIBRARY.relative_to(REPO)), "--validator",
                   str(VALIDATOR.relative_to(REPO))]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        run = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(f"saved processing failed for {suffix}: {(run.stdout + run.stderr)[-2000:]}")
        receipt = json.loads((versions / "v0001/processing.json").read_text())
        if not (receipt["passed"] and receipt["recorded_only"] and receipt["originals_preserved"]
                and receipt["timestamp_joins"]["passed"] and not receipt["missing_evidence"]
                and receipt["final_video_checks"]["passed"]
                and not receipt["physical_acceptance_claimed"]
                and not receipt["legal_acceptance_claimed"]):
            raise ValueError("incomplete saved-only proof for " + suffix)
        receipt_path = ROOT / f"saved-{suffix}-receipt.json"
        log_path = ROOT / f"saved-{suffix}.log"
        dump(receipt_path, receipt)
        log_path.write_text(json.dumps({"command": command, "exit_code": run.returncode,
                                        "receipt_sha256": sha(receipt_path),
                                        "frames": receipt["timestamp_joins"]["frames"],
                                        "originals_preserved": True,
                                        "physical_acceptance_claimed": False},
                                       sort_keys=True) + "\n")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": " ".join(command).replace(str(attempt.relative_to(REPO)), "/external/attempt")
                       .replace(str(versions.relative_to(REPO)), "/external/derived")
                       + " --owner-release-receipt /external/owner-release.json",
            "feedback_command": "cat /external/derived/v*/feedback.json",
            "test_log": log_path.name, "test_log_sha256": sha(log_path),
            "test_exit_code": 0, "test_receipt": receipt_path.name,
            "test_receipt_sha256": sha(receipt_path),
            "test_scope": "diagnostic saved-only processing; no original physical acceptance",
        }
        dump(MANIFEST, manifest)
        print("saved-only passed", suffix)


if __name__ == "__main__":
    main()
