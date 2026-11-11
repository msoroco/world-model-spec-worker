"""Exercise ordered Native ownership closure with synthetic source packets."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT", str(ROOT / ".runtime-work" / "c147331-pipeline-output"))
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.native_output import seal_capture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import (acknowledge_owner_release, copy_sources,
                                               record_native_exit, run as process_saved)


EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def run(case_id):
    manifest = HERE / "execution-manifest.json"
    entry = next((item for item in json.loads(manifest.read_text())["cases"]
                  if item["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("Unknown exact lane case")
    with TemporaryDirectory(prefix="lane-lifecycle-", dir=ROOT / ".runtime-work") as temp:
        base = Path(temp)
        make_fixture(ROOT, ROOT / entry["fixture_recipe"], base / "fixture")
        make_attempt(manifest, case_id, base / "attempt")
        copy_sources(base / "fixture", base / "attempt")
        attempt = base / "attempt"
        (attempt / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "fixture_scope": "synthetic lifecycle protocol only"}) + "\n")
        frames = sum(1 for line in (attempt / "video_frames.jsonl").read_text().splitlines()
                     if line.strip())
        seal = seal_capture(attempt, frames=frames, restoration={"restored": True},
                            errors=[], encoder_exit_codes={name: 0 for name in
                                ("overview", "approach", "reference_corner", "driver_reference")},
                            context={"fixture_scope": "synthetic lifecycle protocol only"})
        if seal["events"] != EVENTS[:3] or seal["diagnostic_fixture"] is not True:
            raise ValueError("Synthetic capture closure not sealed in order")
        native_exit = record_native_exit(attempt)
        if native_exit["event"] != EVENTS[3]:
            raise ValueError("Native exit event missing")
        owner = base / "owner-release.json"
        release = acknowledge_owner_release(attempt, owner, True)
        if release["event"] != EVENTS[4]:
            raise ValueError("Owner release event missing")
        result = process_saved(manifest, case_id, attempt, base / "processing",
                               ROOT / "runtime/library",
                               ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck",
                               owner_receipt=owner)
        receipt = json.loads((base / "processing/v0001/processing.json").read_text())
        if receipt.get("passed") is not True or receipt.get("originals_preserved") is not True:
            raise ValueError("Saved processing did not preserve sealed originals")
        print(" ".join(EVENTS))
        print(case_id, "synthetic_lifecycle_only", "saved_processing_passed")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    run(args.case)
