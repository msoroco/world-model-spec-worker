"""Exercise sealed saved-processing order on explicit synthetic attempts.

Run with SCENARIO_PIPELINE_OUTPUT_ROOT exported under .runtime-work first.
The owner-release acknowledgement applies only to these CPU fixtures.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUTPUT = REPO / ".runtime-work" / "c150530-lifecycle-proof"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    destination = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not destination or not Path(destination).resolve().is_relative_to(REPO / ".runtime-work"):
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
    from worker_exchange.fixture_recipe import materialize as fixture_materialize
    from worker_exchange.runtime_cli import materialize as construction_materialize
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import (acknowledge_owner_release,
                                                  record_native_exit, run)

    manifest = ROOT / "execution-manifest.json"
    for case in ("near_stand", "far_stand", "near_stand_straight"):
        case_id = ROOT.name + "__" + case
        fixture, attempt = OUTPUT / case / "fixture", OUTPUT / case / "attempt"
        if (OUTPUT / case).exists():
            shutil.rmtree(OUTPUT / case)
        fixture_materialize(REPO, ROOT / "cases" / case / "fixture-recipe.json", fixture)
        construction_materialize(manifest, case_id, attempt)
        for item in fixture.iterdir():
            target = attempt / item.name
            if target.exists():
                raise ValueError("Fixture shadows construction: " + item.name)
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        frames = len((attempt / "trace.jsonl").read_text().splitlines())
        seal = seal_capture(attempt, frames=frames,
                            restoration={"restored": True, "synthetic_fixture": True},
                            errors=[], encoder_exit_codes={name: 0 for name in
                                                           ("overview", "approach", "reference_corner", "driver_reference")})
        if seal["diagnostic_fixture"] is not True:
            raise ValueError("Lifecycle fixture lost diagnostic provenance")
        record_native_exit(attempt)
        owner = OUTPUT / case / "synthetic-owner-release.json"
        acknowledge_owner_release(attempt, owner, True)
        output = OUTPUT / case / "saved"
        receipt = run(manifest, case_id, attempt, output, REPO / "runtime/library",
                      REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck",
                      owner)
        if not (receipt["passed"] and receipt["originals_preserved"] and
                receipt["timestamp_joins"]["passed"] and not receipt["missing_evidence"]):
            raise ValueError("Sealed synthetic saved processing incomplete")
        log = ROOT / "cases" / case / "physical-lifecycle.log"
        events = seal["events"] + ["native_exit", "owner_released", "saved_processing_started"]
        log.write_text(json.dumps({"case_id": case_id, "synthetic_fixture": True,
                                   "events": events, "exit_code": 0,
                                   "capture_seal_sha256": sha(attempt / "capture-seal.json"),
                                   "native_exit_sha256": sha(attempt / "native-exit.json"),
                                   "owner_release_sha256": sha(owner),
                                   "processing_sha256": sha(output / "v0001/processing.json")}, indent=2) + "\n")
        proof_path = ROOT / "cases" / case / "physical-preparation.partial.json"
        proof = json.loads(proof_path.read_text())
        proof["lifecycle"] = {"events": events, "exit_code": 0,
                              "log": log.relative_to(ROOT).as_posix(),
                              "log_sha256": sha(log),
                              "command": "export SCENARIO_PIPELINE_OUTPUT_ROOT=\"$PWD/.runtime-work/c150530-lifecycle-proof-output\"; PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + ROOT.name + "/prove_synthetic_lifecycle.py",
                              "scope": "controlled synthetic fixture, no actual owner release"}
        proof_path.write_text(json.dumps(proof, indent=2) + "\n")
        print(case, "synthetic lifecycle passed", flush=True)


if __name__ == "__main__":
    main()
