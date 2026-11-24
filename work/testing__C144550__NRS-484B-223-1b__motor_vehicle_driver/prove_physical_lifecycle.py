"""Test Native closure and owner-release ordering with synthetic CPU sources."""

import hashlib
import json
import os
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    from scenario_pipeline.worker_exchange.saved_processing import (
        _closure, acknowledge_owner_release, record_native_exit,
    )

    attempt = Path(output) / "physical-lifecycle-attempt"
    if attempt.exists():
        shutil.rmtree(attempt)
    attempt.mkdir(parents=True)
    shutil.copyfile(HERE / "construction.json", attempt / "construction.json")
    shutil.copyfile(HERE / "runner.py", attempt / "runner.py")
    revision = {"construction_sha256": sha(attempt / "construction.json"),
                "runner_sha256": sha(attempt / "runner.py")}
    seal = {"events": EVENTS[:3], "sources": {}, "native_revision": revision,
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}
    (attempt / "capture-seal.json").write_text(json.dumps(seal) + "\n")
    owner_path = attempt / "owner-release.json"
    try:
        acknowledge_owner_release(attempt, owner_path, True)
    except ValueError as error:
        if "has not exited" not in str(error):
            raise
    else:
        raise ValueError("Owner release before Native exit was accepted")
    exit_receipt = record_native_exit(attempt)
    owner_receipt = acknowledge_owner_release(attempt, owner_path, True)
    _closure(attempt, owner_path, "native", False)
    if exit_receipt["event"] != "native_exit" or owner_receipt["event"] != "owner_released":
        raise ValueError("Native closure sequence changed")
    print(json.dumps({"events": EVENTS, "exit_code": 0,
                      "negative_pre_exit_rejected": True,
                      "closure_verified": True,
                      "synthetic_fixture": True}))


if __name__ == "__main__":
    main()
