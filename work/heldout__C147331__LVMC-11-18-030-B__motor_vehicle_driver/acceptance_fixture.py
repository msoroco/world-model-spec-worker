"""CPU acceptance protocol using synthetic sources and mock pixel declarations."""

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
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from delivery_audit import audit_attempt
from lane_finalizer import analyze
from lane_physical_outcome import check_physical_outcome
from physical_fixture import _advance_source, rows


def run(case_id, negative=False):
    manifest = HERE / "execution-manifest.json"
    entry = next((item for item in json.loads(manifest.read_text())["cases"]
                  if item["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("Unknown exact lane case")
    with TemporaryDirectory(prefix="lane-acceptance-", dir=ROOT / ".runtime-work") as temp:
        base = Path(temp)
        make_fixture(ROOT, ROOT / entry["fixture_recipe"], base / "fixture")
        make_attempt(manifest, case_id, base / "attempt")
        copy_sources(base / "fixture", base / "attempt")
        attempt = base / "attempt"
        _advance_source(attempt, "complete_motion")
        report = analyze(attempt, write_channel=False)
        audit = audit_attempt(attempt, report)
        pixel_review = {"case_id": case_id,
                        "cameras": {name: {
                            "source_sha256": detail["source_sha256"],
                            "reviewed_frames": audit["frame_count"],
                            "required_markings_visible": True,
                            "required_bodies_visible": True}
                            for name, detail in audit["camera_decodes"].items()}}
        if negative:
            pixel_review["cameras"]["approach"]["source_sha256"] = "stale synthetic source"
        result = check_physical_outcome(audit, report, pixel_review,
                                        rows(attempt / "trace.jsonl"))
        print(json.dumps({"fixture_only": True, "case_id": case_id,
                          "source_frame_count": audit["frame_count"],
                          "source_decoded_cameras": list(audit["camera_decodes"]),
                          "outcome_checker": result,
                          "actual_visibility_verified": False,
                          "physical_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    run(args.case, args.negative)
