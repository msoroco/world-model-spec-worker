"""Exercise original motion outcomes and the Native owner-release lifecycle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from private_way_motion import measure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def run(case_id, kind, output):
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("unknown physical outcome")
    variant = case_id.removeprefix(HERE.name + "__")
    if case_id != HERE.name + "__" + variant:
        raise ValueError("wrong physical case")
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if REPO / ".runtime-work" not in scratch.parents:
        raise ValueError("physical scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    diagnostic = json.loads((HERE / "diagnostics" / variant / "diagnostic.json").read_text())
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        stage = Path(temporary)
        for name, content in diagnostic["files"].items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        source = stage / "original-attempt"
        motion = source / "motion.jsonl"
        if kind == "incomplete_motion":
            rows = [json.loads(line) for line in motion.read_text().splitlines()]
            for row in rows:
                row["ego_on_highway"] = False
                row["ego_speed_mps"] = 0
            motion.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
            seal_path = source / "motion-seal.json"
            seal = json.loads(seal_path.read_text())
            seal["motion_sha256"] = sha(motion)
            seal_path.write_text(dump(seal))
        elif kind == "missing_evidence":
            motion.unlink()
        measured = None
        error = None
        try:
            measured = measure(source, case_id)
            status = "met" if measured["first_highway_frame"] >= 0 else "not_met"
        except ValueError as failure:
            error = str(failure)
            if kind == "incomplete_motion" and "ego never reached" in error:
                status = "not_met"
            elif kind == "missing_evidence" and "Missing required original source: motion.jsonl" in error:
                status = "unverified"
            else:
                raise
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError("physical outcome mismatch")
        sources = {name: sha(source / name) for name in
                   ("motion.jsonl", "motion-seal.json", "site.json", "frame-map.json")
                   if (source / name).is_file()}
        result = {
            "case_id": case_id,
            "physical_checks": {"maneuver": {
                "status": status,
                "method": "sealed original-frame highway entry and complete approaching actor motion",
                "sources": sources, "error": error,
                "legal_verdict_claimed": False,
            }},
            "maneuver_completed": status == "met",
            "realized_observables": {} if measured is None else {
                "first_highway_frame": measured["first_highway_frame"],
                "highway_actor_ids": measured["highway_actor_ids"],
                "approach_first_last_distance_m": measured["approach_first_last_distance_m"],
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
            from worker_exchange.saved_processing import (record_native_exit,
                                                           acknowledge_owner_release,
                                                           copy_sources)
            (stage / "runner.py").write_text((HERE / "runner.py").read_text())
            (stage / "construction.json").write_text(
                (HERE / "cases" / variant / "construction.json").read_text())
            (stage / "acquisition-provenance.json").write_text(dump({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "physical_acceptance_claimed": False}))
            seal_capture(stage, frames=9,
                         restoration={"restored": True, "settings_readback": "synthetic CPU closure fixture"},
                         errors=[], encoder_exit_codes={"fixture": 0})
            native_exit = record_native_exit(stage)
            owner = acknowledge_owner_release(stage, stage / "owner-release.json", True)
            with tempfile.TemporaryDirectory(dir=scratch) as saved:
                copy_sources(stage, Path(saved))
            if native_exit["capture_seal_sha256"] != sha(stage / "capture-seal.json") or \
                    owner["native_exit_sha256"] != sha(stage / "native-exit.json"):
                raise ValueError("Native lifecycle identity changed")
            lifecycle = ["capture_finished", "encoders_closed", "restoration_verified",
                         "native_exit", "owner_released", "saved_processing_started"]
        print(json.dumps({"case_id": case_id, "kind": kind, "status": status,
                          "lifecycle": lifecycle, "diagnostic_fixture": True,
                          "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.case, args.kind, args.output)
