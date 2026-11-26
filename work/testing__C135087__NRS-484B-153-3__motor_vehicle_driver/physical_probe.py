"""Exercise source-bound door completion and Native closure ordering on CPU fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from door_measurement import measure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
SOURCES = ("frame_map", "door", "activity", "passing_vehicle", "geometry")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case_id: str, kind: str, output: Path):
    if kind not in KINDS or case_id not in {case["case_id"] for case in
            json.loads((HERE / "case-plan.json").read_text())["cases"]}:
        raise ValueError("exact case or fixture kind missing")
    root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if REPO / ".runtime-work" not in root.parents and root != REPO / ".runtime-work":
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    temp_root = REPO / ".runtime-work/c135087-owner-nov26/temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    label = case_id.removeprefix(HERE.name + "__")
    source = HERE / "cases" / label / "diagnostic-sources"
    with tempfile.TemporaryDirectory(dir=temp_root) as temporary:
        stage = Path(temporary)
        for name in SOURCES + ("inventory",):
            shutil.copyfile(source / (name + ".json"), stage / (name + ".json"))
        inventory = json.loads((stage / "inventory.json").read_text())
        if kind == "incomplete_motion":
            packet = json.loads((stage / "passing_vehicle.json").read_text())
            for row in packet["samples"]:
                row["center_x_m"] = -8
            path = stage / "passing_vehicle.json"
            path.write_text(json.dumps(packet, sort_keys=True, indent=2) + "\n")
            inventory["sources"]["passing_vehicle"]["sha256"] = _sha(path)
        elif kind == "missing_evidence":
            (stage / "door.json").unlink()
        status = "unverified"
        measured = None
        error = None
        try:
            measured = measure(stage, inventory, case_id, HERE / "case-plan.json")
            status = "met"
        except ValueError as failure:
            error = str(failure)
            if kind == "incomplete_motion" and "door-window traversal" in error:
                status = "not_met"
            elif kind == "missing_evidence" and "source missing" in error:
                status = "unverified"
            else:
                raise
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError("physical source outcome differs: " + kind)
        sources = {name: _sha(stage / (name + ".json")) for name in SOURCES
                   if (stage / (name + ".json")).is_file()}
        check = {"status": status,
                 "method": "original door/articulation, activity and passing-body source remeasurement",
                 "sources": sources, "intervals": [] if measured is None else [
                     [measured["open_start_frame"], measured["closed_after_frame"]]],
                 "error": error, "physical_causation_claimed": False}
        result = {"case_id": case_id, "physical_checks": {"maneuver": check},
                  "maneuver_completed": status == "met",
                  "realized_observables": {} if measured is None else {
                      "open_duration_s": {"value": measured["open_duration_s"], "unit": "s",
                                          "method": "source-bound original frame interval",
                                          "statistic": "open frames / 20 Hz",
                                          "time_window": "observed door-open interval",
                                          "reference": "door.json"},
                      "inactive_open_duration_s": {"value": measured["inactive_open_duration_s"],
                                                   "unit": "s", "method": "source-bound loading activity",
                                                   "statistic": "inactive open frames / 20 Hz",
                                                   "time_window": "observed door-open interval",
                                                   "reference": "activity.json"}},
                  "measured_door_episode": measured, "provenance_kind": "synthetic_fixture",
                  "diagnostic_fixture": True, "physical_acceptance_claimed": False,
                  "legal_judgment": None}
        Path(output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        lifecycle = None
        if kind == "complete_motion":
            sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
            from worker_exchange.native_output import seal_capture
            from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
            construction = json.loads((HERE / "cases" / label / "construction.json").read_text())
            config = json.loads(next(item["content"] for item in construction["files"] if item["path"] == "config.json"))
            for name, value in (("construction.json", construction), ("config.json", config)):
                (stage / name).write_text(json.dumps(value, sort_keys=True) + "\n")
            (stage / "runner.py").write_text((HERE / "runner.py").read_text())
            (stage / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "physical_acceptance_claimed": False}) + "\n")
            (stage / "trace.jsonl").write_text("".join(json.dumps({"frame": i + 100,
                "time_s": i / 20, "passing_position_m": [-8 + i * .3, 2.2, 0]}) + "\n"
                for i in range(60)))
            (stage / "video_frames.jsonl").write_text("".join(json.dumps({
                "video_frame": i, "carla_frame": i + 100, "native_frame": i + 100,
                "time_s": i / 20}) + "\n" for i in range(60)))
            seal = seal_capture(stage, frames=60, restoration={"restored": True,
                "settings_readback": "synthetic CPU closure fixture"}, errors=[],
                encoder_exit_codes={"fixture": 0})
            native_exit = record_native_exit(stage)
            owner = acknowledge_owner_release(stage, stage / "owner-release.json", True)
            with tempfile.TemporaryDirectory(dir=temp_root) as saved:
                copy_sources(stage, Path(saved))
            if native_exit["capture_seal_sha256"] != _sha(stage / "capture-seal.json") or owner[
                    "native_exit_sha256"] != _sha(stage / "native-exit.json"):
                raise ValueError("Native closure receipts differ")
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
