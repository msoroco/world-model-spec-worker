"""Exercise U-turn physical-state and Native closure logic on CPU fixtures."""
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case_id, kind, output):
    plan = json.loads((HERE / "case-plan.json").read_text())
    if kind not in KINDS or case_id not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("exact U-turn case or fixture kind missing")
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if REPO / ".runtime-work" not in output_root.parents and output_root != REPO / ".runtime-work":
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    temp_root = REPO / ".runtime-work/c133321-owner-nov26/temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    name = case_id.removeprefix(HERE.name + "__")
    source = HERE / "cases" / name / "diagnostic-sources"
    with tempfile.TemporaryDirectory(dir=temp_root) as temporary:
        stage = Path(temporary)
        for packet in ("map", "history", "inventory"):
            shutil.copyfile(source / (packet + ".json"), stage / (packet + ".json"))
        (stage / "fixture-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        construction = json.loads((HERE / "cases" / name / "construction.json").read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        for filename, value in (("construction.json", construction), ("config.json", config)):
            (stage / filename).write_text(json.dumps(value, sort_keys=True) + "\n")
        if kind == "incomplete_motion":
            packet = json.loads((stage / "history.json").read_text())
            for row in packet["frames"]:
                if row["section"] == "exit":
                    row["heading_x"] = 1
            path = stage / "history.json"
            path.write_text(json.dumps(packet, sort_keys=True) + "\n")
            inventory = json.loads((stage / "inventory.json").read_text())
            inventory["sources"]["history"]["sha256"] = _sha(path)
            (stage / "inventory.json").write_text(json.dumps(inventory, sort_keys=True) + "\n")
        elif kind == "missing_evidence":
            (stage / "history.json").unlink()
        status, measured, error = "unverified", None, None
        try:
            measured = measure(stage)
            status = "met" if (measured["requested_lane_observed"] and
                               not measured["other_ring_lane_observed"] and
                               measured["opposite_departure_observed"]) else "not_met"
        except ValueError as failure:
            error = str(failure)
            if kind != "missing_evidence" or "Missing required source" not in error:
                raise
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError("physical fixture outcome differs: " + kind)
        result = {"case_id": case_id,
                  "physical_checks": {"maneuver": {"status": status,
                     "method": "source-bound original lane and exit-heading remeasurement",
                     "sources": {name: _sha(stage / (name + ".json"))
                                 for name in ("map", "history")
                                 if (stage / (name + ".json")).is_file()},
                     "error": error, "physical_causation_claimed": False}},
                  "maneuver_completed": status == "met",
                  "realized_observables": {} if measured is None else {
                      "ring_frame_count": {"value": measured["ring_frame_count"],
                                           "unit": "frames", "method": "original actor map-lane history",
                                           "statistic": "ring-frame count",
                                           "time_window": "observed circular traversal",
                                           "reference": "history.json"}},
                  "measured_u_turn": measured,
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
            (stage / "trace.jsonl").write_text("".join(json.dumps({"frame": i + 100,
                "time_s": i / 20, "lane_id": measured["requested_lane_id"]}) + "\n"
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
            if native_exit["capture_seal_sha256"] != _sha(stage / "capture-seal.json") or owner[
                    "native_exit_sha256"] != _sha(stage / "native-exit.json"):
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
