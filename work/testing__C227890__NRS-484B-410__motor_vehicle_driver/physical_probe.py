"""CPU diagnostic outcomes from sealed parked departure activity and Native ownership closure."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from parked_activity import measure_original_activity

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def run(case_id, kind, output):
    if kind not in KINDS or case_id not in {item["case_id"] for item in json.loads((HERE / "case-plan.json").read_text())["cases"]}:
        raise ValueError("wrong exact case or outcome")
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if REPO / ".runtime-work" not in scratch.parents:
        raise ValueError("physical scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    variant = case_id.removeprefix(HERE.name + "__")
    spec = json.loads((HERE / ("diagnostic-" + variant + ".json")).read_text())
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        stage = Path(temporary)
        source = stage / "original-attempt"
        source.mkdir()
        for name, content in spec["files"].items():
            if name.startswith("original-attempt/"):
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
        activity = source / "activity.jsonl"
        seal = source / "activity-seal.json"
        inventory_path = source / "inventory.json"
        if kind == "incomplete_motion":
            rows = [json.loads(line) for line in activity.read_text().splitlines()]
            for row in rows:
                row["ego_speed_mps"] = 0.0
                row["ego_in_reviewed_parking_bay"] = True
            activity.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
            sealed = json.loads(seal.read_text())
            sealed["history_sha256"] = sha(activity)
            seal.write_text(dump(sealed))
            inventory = json.loads(inventory_path.read_text())
            inventory["activity_sha256"] = sha(activity)
            inventory["source_sha256"]["activity-seal.json"] = sha(seal)
            inventory_path.write_text(dump(inventory))
        elif kind == "missing_evidence":
            activity.unlink()
        measured = None
        error = None
        try:
            measured = measure_original_activity(activity, seal, case_id, diagnostic=True)
            status = "met" if measured["intervals_s"]["parked"] and measured["intervals_s"]["moving"] else "not_met"
        except (ValueError, FileNotFoundError) as failure:
            error = str(failure)
            if kind != "missing_evidence" or "missing original activity source" not in error:
                raise
            status = "unverified"
        expected = {"complete_motion": "met", "incomplete_motion": "not_met", "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError("physical outcome mismatch: " + kind + " " + status)
        sources = {name: sha(source / name) for name in ("activity.jsonl", "activity-seal.json", "inventory.json", "frame-map.json") if (source / name).is_file()}
        result = {
            "case_id": case_id,
            "physical_checks": {"maneuver": {
                "status": status,
                "method": "sealed source-frame parked state and departure remeasurement; engineering movement check only",
                "sources": sources,
                "error": error,
                "legal_verdict_claimed": False,
            }},
            "maneuver_completed": status == "met",
            "realized_observables": {} if measured is None else {
                "parked_intervals_s": {"value": measured["intervals_s"]["parked"], "method": "sealed 20 Hz activity history", "reference": "original-attempt/activity.jsonl"},
                "moving_intervals_s": measured["intervals_s"]["moving"],
                "approach_intervals_s": measured["intervals_s"]["other_approaching"],
            },
            "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True,
            "physical_acceptance_claimed": False,
            "legal_judgment": None,
        }
        Path(output).write_text(dump(result))
        lifecycle = None
        if kind == "complete_motion":
            sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
            from worker_exchange.native_output import seal_capture
            from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources

            (stage / "runner.py").write_text((HERE / "runner.py").read_text())
            (stage / "construction.json").write_text((HERE / "cases" / variant / "construction.json").read_text())
            (stage / "acquisition-provenance.json").write_text(dump({"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True, "physical_acceptance_claimed": False}))
            frames = json.loads((source / "frame-map.json").read_text())["frames"]
            (stage / "trace.jsonl").write_text("".join(json.dumps({"frame": row["native_frame"], "time_s": row["native_time_s"], "speed_mps": 0}) + "\n" for row in frames))
            (stage / "video_frames.jsonl").write_text("".join(json.dumps({"video_frame": index, "carla_frame": row["native_frame"], "native_frame": row["native_frame"], "time_s": row["native_time_s"]}) + "\n" for index, row in enumerate(frames)))
            seal_capture(stage, frames=9, restoration={"restored": True, "settings_readback": "synthetic CPU closure fixture"}, errors=[], encoder_exit_codes={"fixture": 0})
            native_exit = record_native_exit(stage)
            owner = acknowledge_owner_release(stage, stage / "owner-release.json", True)
            with tempfile.TemporaryDirectory(dir=scratch) as saved:
                copy_sources(stage, Path(saved))
            if native_exit["capture_seal_sha256"] != sha(stage / "capture-seal.json") or owner["native_exit_sha256"] != sha(stage / "native-exit.json"):
                raise ValueError("Native lifecycle identity changed")
            lifecycle = ["capture_finished", "encoders_closed", "restoration_verified", "native_exit", "owner_released", "saved_processing_started"]
        print(json.dumps({"case_id": case_id, "kind": kind, "status": status, "lifecycle": lifecycle, "diagnostic_fixture": True, "physical_acceptance_claimed": False}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.case, args.kind, args.output)


if __name__ == "__main__":
    main()
