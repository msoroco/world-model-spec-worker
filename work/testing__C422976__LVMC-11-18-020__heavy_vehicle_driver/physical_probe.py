"""Exercise School-Xing physical completion and Native closure on CPU fixtures."""
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
import school_crossing as school

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case_id, kind, output):
    plan = json.loads((HERE / "case-plan.json").read_text())
    if kind not in KINDS or case_id not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("exact School-Xing case or physical fixture kind missing")
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if REPO / ".runtime-work" not in output_root.parents:
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    temp_root = REPO / ".runtime-work/c422976-owner/temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    name = case_id.removeprefix(HERE.name + "__")
    case = next(c for c in school.CASES if c.name == name)
    source = HERE / "cases" / name / "diagnostic-sources"
    with tempfile.TemporaryDirectory(dir=temp_root) as temporary:
        stage = Path(temporary)
        for filename in ("site.json", "history.json", "frame-map.json", "inventory.json"):
            shutil.copyfile(source / filename, stage / filename)
        (stage / "fixture-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        construction = json.loads((HERE / "cases" / name / "construction.json").read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        for filename, value in (("construction.json", construction), ("config.json", config)):
            (stage / filename).write_text(json.dumps(value, sort_keys=True) + "\n")
        if kind == "incomplete_motion":
            frames = json.loads((stage / "history.json").read_text())
            for index, row in enumerate(frames):
                row["vehicle_front_xy"] = ([.5, 0.] if index >= 4 else [-1., 0.]) \
                    if not case.entry_requested else [-1., 0.]
            path = stage / "history.json"
            path.write_text(json.dumps(frames, sort_keys=True) + "\n")
            inventory = json.loads((stage / "inventory.json").read_text())
            inventory["sources"]["history"]["sha256"] = sha(path)
            (stage / "inventory.json").write_text(json.dumps(inventory, sort_keys=True) + "\n")
        elif kind == "missing_evidence":
            (stage / "history.json").unlink()
        status, measured, error = "unverified", None, None
        try:
            _, measured, _, _, _ = measure(stage)
            entered = measured["entry"] is not None
            status = "met" if entered is case.entry_requested else "not_met"
        except ValueError as failure:
            error = str(failure)
            if kind != "missing_evidence" or "Missing required source" not in error:
                raise
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError("physical School-Xing fixture outcome differs: " + kind)
        result = {"case_id": case_id,
            "physical_checks": {"maneuver": {"status": status,
                "method": "source-bound original heavy-vehicle front, sign, person and crossing remeasurement",
                "sources": {filename: sha(stage / filename)
                            for filename in ("site.json", "history.json", "frame-map.json")
                            if (stage / filename).is_file()},
                "error": error, "physical_causation_claimed": False}},
            "maneuver_completed": status == "met",
            "realized_observables": {} if measured is None else {
                "crosswalk_entry_frame": {"value": measured["entry"]["frame"] if measured["entry"] else None,
                    "unit": "original_frame", "method": "original front extent history",
                    "statistic": "first physical crossing entry", "time_window": "approach",
                    "reference": "history.json"}},
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_acceptance_claimed": False, "legal_judgment": None}
        Path(output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        lifecycle = None
        if kind == "complete_motion":
            sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
            from worker_exchange.native_output import seal_capture
            from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
            (stage / "runner.py").write_text((HERE / "runner.py").read_text())
            (stage / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "physical_acceptance_claimed": False}) + "\n")
            (stage / "trace.jsonl").write_text("".join(json.dumps({
                "frame": i + 100, "time_s": i / 20, "speed_mps": 1.}) + "\n"
                for i in range(9)))
            (stage / "video_frames.jsonl").write_text("".join(json.dumps({
                "video_frame": i, "carla_frame": i + 100, "native_frame": i + 100,
                "time_s": i / 20}) + "\n" for i in range(9)))
            seal = seal_capture(stage, frames=9, restoration={"restored": True,
                "settings_readback": "synthetic CPU closure fixture"}, errors=[],
                encoder_exit_codes={"fixture": 0})
            native_exit = record_native_exit(stage)
            owner = acknowledge_owner_release(stage, stage / "owner-release.json", True)
            with tempfile.TemporaryDirectory(dir=temp_root) as saved:
                copy_sources(stage, Path(saved))
            if native_exit["capture_seal_sha256"] != sha(stage / "capture-seal.json") or \
                    owner["native_exit_sha256"] != sha(stage / "native-exit.json"):
                raise ValueError("Native lifecycle closure receipts differ")
            lifecycle = seal["events"] + ["native_exit", "owner_released", "saved_processing_started"]
        return {"case_id": case_id, "kind": kind, "status": status,
                "diagnostic_fixture": True, "physical_acceptance_claimed": False,
                "lifecycle": lifecycle}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
