"""CPU outcome fixtures for the rail capture and Native closure protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from rail_diagnostic_measurement import verify_diagnostic
from rail_saved_measurement import _source
from rail_sight_measurement import measure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def stage_fixture(root, key):
    folder = HERE / "diagnostic-fixtures" / key
    spec = json.loads((folder / "fixture-spec.json").read_text())
    for relative, content in spec["files"].items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    for row in json.loads((folder / "fixture-recipe.json").read_text())["sources"]:
        if row["path"] != "native-rail-camera-map.json":
            continue
        source = REPO / row["source"]
        if sha(source) != row["sha256"]:
            raise ValueError("rail camera-map recipe source changed")
        (root / row["path"]).write_bytes(source.read_bytes())


def run(case_id, kind, output):
    plan = json.loads((HERE / "case-plan.json").read_text())
    if kind not in KINDS or case_id not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("exact rail case or fixture kind missing")
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    scratch = REPO / ".runtime-work"
    if scratch not in output_root.parents:
        raise ValueError("runtime output root must be under .runtime-work")
    temporary = scratch / "c410753-physical-temp"
    temporary.mkdir(parents=True, exist_ok=True)
    key = case_id.removeprefix(HERE.name + "__")
    with tempfile.TemporaryDirectory(dir=temporary) as name:
        stage = Path(name)
        stage_fixture(stage, key)
        receipt = json.loads((stage / "native-rail-receipt.json").read_text())
        packet = json.loads(_source(stage, receipt["packet"]).read_text())
        frame_path = stage / "native-rail-frames.json"
        original_digest = sha(frame_path)
        frames = json.loads(frame_path.read_text())
        measured = None
        error = None
        if kind == "complete_motion":
            measured = verify_diagnostic(stage, receipt, packet, case_id)["observation"]
            status = "met" if len(measured["crossing_original_frames"]) >= 3 else "not_met"
        elif kind == "incomplete_motion":
            for row in frames:
                if row["body_on_crossing"]:
                    row["body_on_crossing"] = False
                    source = stage / row["frame_source_path"]
                    original = json.loads(source.read_text())
                    original["body_on_crossing"] = False
                    write(source, original)
                    row["frame_source_sha256"] = sha(source)
            write(frame_path, frames)
            try:
                road = _source(stage, packet["original_map_source"]).read_text()
                measure(stage, packet, road, frames)
            except ValueError as failure:
                error = str(failure)
            if error != "complete continuous grade-crossing traversal missing":
                raise ValueError("incomplete rail motion was not measured")
            status = "not_met"
        else:
            frame_path.unlink()
            try:
                _source(stage, receipt["frames"])
            except ValueError as failure:
                error = str(failure)
            if not error:
                raise ValueError("missing rail source was accepted")
            status = "unverified"
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError("rail physical fixture outcome differs")
        result = {"case_id": case_id, "kind": kind,
                  "physical_checks": {"maneuver": {
                      "status": status,
                      "method": "source-bound 900-frame crossing occupancy and traversal measurement",
                      "sources": {"original_native_rail_frames_sha256": original_digest,
                                  "fixture_native_rail_frames_sha256": sha(frame_path) if frame_path.exists() else None,
                                  "original_capture_receipt_sha256": sha(stage / "native-rail-receipt.json")},
                      "error": error}},
                  "maneuver_completed": status == "met",
                  "realized_observables": {} if measured is None else {
                      "crossing_frames": {"value": len(measured["crossing_original_frames"]),
                                          "unit": "frames", "method": "source-bound occupancy",
                                          "statistic": "count", "time_window": "traversal",
                                          "reference": "native-rail-frames.json"},
                      "speed_mph_max": {"value": measured["traversal_speed_mph_max"],
                                        "unit": "mph", "method": "original speed readback",
                                        "statistic": "maximum", "time_window": "traversal",
                                        "reference": "native-rail-frames.json"}},
                  "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                  "physical_acceptance_claimed": False, "legal_judgment": None}
        write(output, result)
        lifecycle = None
        if kind == "complete_motion":
            sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
            from worker_exchange.native_output import seal_capture
            from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
            (stage / "runner.py").write_text((HERE / "runner.py").read_text())
            (stage / "construction.json").write_bytes(
                (HERE / "cases" / key / "construction.json").read_bytes())
            (stage / "config.json").write_bytes(
                (HERE / "cases" / key / "config.json").read_bytes())
            write(stage / "acquisition-provenance.json", {
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "physical_acceptance_claimed": False})
            (stage / "trace.jsonl").write_text("".join(json.dumps({
                "frame": i, "time_s": i / 20, "speed_mps": 1.0}) + "\n" for i in range(9)))
            (stage / "video_frames.jsonl").write_text("".join(json.dumps({
                "video_frame": i, "carla_frame": i, "native_frame": i,
                "time_s": i / 20}) + "\n" for i in range(9)))
            seal = seal_capture(stage, frames=9, restoration={"restored": True,
                "settings_readback": "synthetic CPU closure fixture"}, errors=[],
                encoder_exit_codes={"fixture": 0})
            exit_receipt = record_native_exit(stage)
            owner = acknowledge_owner_release(stage, stage / "owner-release.json", True)
            with tempfile.TemporaryDirectory(dir=temporary) as saved:
                copy_sources(stage, Path(saved))
            if exit_receipt["capture_seal_sha256"] != sha(stage / "capture-seal.json") or \
                    owner["native_exit_sha256"] != sha(stage / "native-exit.json"):
                raise ValueError("rail Native closure receipts differ")
            lifecycle = seal["events"] + ["native_exit", "owner_released",
                                          "saved_processing_started"]
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
