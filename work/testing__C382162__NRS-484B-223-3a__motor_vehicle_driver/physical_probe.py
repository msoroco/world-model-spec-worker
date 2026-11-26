"""CPU physical-outcome and Native ownership-closure fixture checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from analysis import measure
from native_capture import ASSIGNMENT, KINDS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c382162-owner/temp"
OUTCOMES = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case_id, kind, output):
    if case_id not in {ASSIGNMENT + "__" + name for name in KINDS} or kind not in OUTCOMES:
        raise ValueError("exact center-lane fixture identity differs")
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if REPO / ".runtime-work" not in output_root.parents:
        raise ValueError("runtime output root must remain in .runtime-work")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    name = case_id.removeprefix(ASSIGNMENT + "__")
    source = HERE / "cases" / name / "diagnostic-sources"
    with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
        stage = Path(temporary)
        shutil.copytree(source, stage, dirs_exist_ok=True)
        construction = json.loads((HERE / "cases" / name / "construction.json").read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        (stage / "config.json").write_text(json.dumps(config) + "\n")
        (stage / "construction.json").write_text(json.dumps(construction) + "\n")
        (stage / "road.xodr").write_text(json.loads((HERE / "diagnostic-scaffold.json").read_text())["files"]["road.xodr"])
        (stage / "fixture-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        trace = json.loads((HERE / "diagnostic-scaffold.json").read_text())["files"]["trace.jsonl"]
        (stage / "trace.jsonl").write_text(trace)
        if kind == "incomplete_motion":
            history = json.loads((stage / "native/history.json").read_text())
            for row in history:
                if row["lane_id"] == "C":
                    row["lane_id"] = "E"
            path = stage / "native/history.json"
            path.write_text(json.dumps(history) + "\n")
            inventory = json.loads((stage / "native/inventory.json").read_text())
            inventory["sources"]["history"]["sha256"] = sha(path)
            (stage / "native/inventory.json").write_text(json.dumps(inventory) + "\n")
        elif kind == "missing_evidence":
            (stage / "native/history.json").unlink()
        measured = None
        error = None
        try:
            _, measured, _, _, _, _ = measure(stage)
            status = "met" if measured["center_lane_occupancy_frames"] else "not_met"
        except ValueError as failure:
            error = str(failure)
            if kind == "incomplete_motion" and "actual center-lane occupancy absent" in error:
                status = "not_met"
            elif kind == "missing_evidence" and "Missing required source" in error:
                status = "unverified"
            else:
                raise
        if status != {"complete_motion": "met", "incomplete_motion": "not_met",
                      "missing_evidence": "unverified"}[kind]:
            raise ValueError("physical fixture classification differs")
        result = {"case_id": case_id, "physical_checks": {"maneuver": {
            "status": status, "method": "source-sealed Native lane and route remeasurement",
            "sources": {name: sha(stage / name) for name in
                        ("native/site.json", "pre-entry-intent.json", "native/history.json")
                        if (stage / name).is_file()}, "error": error,
            "physical_causation_claimed": False}}, "maneuver_completed": status == "met",
            "realized_observables": {} if measured is None else {
                "center_lane_occupancy_frames": {"value": measured["center_lane_occupancy_frames"],
                    "unit": "original_frame", "method": "original lane readback",
                    "statistic": "actual occupied frames", "time_window": "route",
                    "reference": "native/history.json"}},
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_acceptance_claimed": False, "legal_judgment": None}
        Path(output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        lifecycle = None
        if kind == "complete_motion":
            sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
            from worker_exchange.native_output import seal_capture
            from worker_exchange.saved_processing import (record_native_exit,
                acknowledge_owner_release, copy_sources)
            (stage / "runner.py").write_text((HERE / "runner.py").read_text())
            (stage / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "physical_acceptance_claimed": False}) + "\n")
            mapping = json.loads((HERE / "diagnostic-scaffold.json").read_text())["files"]["video_frames.jsonl"]
            (stage / "video_frames.jsonl").write_text(mapping)
            seal = seal_capture(stage, frames=9, restoration={"restored": True,
                "settings_readback": "synthetic CPU closure fixture"}, errors=[],
                encoder_exit_codes={"fixture": 0})
            native_exit = record_native_exit(stage)
            owner = acknowledge_owner_release(stage, stage / "owner-release.json", True)
            with tempfile.TemporaryDirectory(dir=SCRATCH) as saved:
                copy_sources(stage, Path(saved))
            if native_exit["capture_seal_sha256"] != sha(stage / "capture-seal.json") or \
                    owner["native_exit_sha256"] != sha(stage / "native-exit.json"):
                raise ValueError("Native closure receipt differs")
            lifecycle = seal["events"] + ["native_exit", "owner_released", "saved_processing_started"]
        return {"case_id": case_id, "kind": kind, "status": status,
                "diagnostic_fixture": True, "physical_acceptance_claimed": False,
                "lifecycle": lifecycle}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=OUTCOMES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
