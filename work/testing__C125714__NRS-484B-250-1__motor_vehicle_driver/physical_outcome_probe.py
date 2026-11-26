"""Seven exact crossing cases: met, stalled and missing original-source probes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = ("precedence", "advance", "other_later", "opposite_straight",
         "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")
SOURCES = ("config.json", "construction.json", "runner.py", "trace.jsonl",
           "video_frames.jsonl", "ego-body-history.jsonl", "intersection-context.json",
           "acquisition-provenance.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path, values):
    path.write_text("".join(json.dumps(value, allow_nan=False) + "\n"
                            for value in values))


def stall(folder):
    body_path = folder / "ego-body-history.jsonl"
    bodies = read_rows(body_path)
    first = bodies[0]["body_vertices_xy_m"]
    for body in bodies:
        body["body_vertices_xy_m"] = first
    write_rows(body_path, bodies)
    trace_path = folder / "trace.jsonl"
    traces = read_rows(trace_path)
    first_position = traces[0].get("position_m")
    for trace in traces:
        trace["position_m"] = first_position
        trace["speed_mps"] = 0
    write_rows(trace_path, traces)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    source, output = Path(args.source).resolve(), Path(args.output).resolve()
    for path in (output_root, source, output):
        if not path.is_relative_to((REPO / ".runtime-work").resolve()):
            raise ValueError("physical diagnostic paths must be under .runtime-work")
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
        acknowledge_owner_release, copy_sources)

    output.mkdir(parents=True, exist_ok=False)
    receipts = []
    for kind in CASES:
        origin = source / kind
        if (origin / "positive").is_dir():
            origin = origin / "positive"
        if not (origin / "compatibility.json").is_file():
            raise ValueError("exact current compatibility attempt required: " + kind)
        compatibility = json.loads((origin / "compatibility.json").read_text())
        if (compatibility.get("passed") is not True or
                compatibility.get("case_id") != ROOT.name + "__" + kind or
                compatibility.get("construction_sha256") != sha(origin / "construction.json")):
            raise ValueError("physical source differs from current construction: " + kind)
        original_result = json.loads((origin / "result.json").read_text())
        case_root = output / kind
        case_root.mkdir()
        recorded = []
        for label, expected in (("complete_motion", "met"),
                                ("incomplete_motion", "not_met"),
                                ("missing_evidence", "unverified")):
            folder = case_root / label
            folder.mkdir()
            for name in SOURCES:
                source_file = origin / name
                if source_file.is_file():
                    shutil.copy2(source_file, folder / name)
            if label == "incomplete_motion":
                stall(folder)
            elif label == "missing_evidence":
                (folder / "ego-body-history.jsonl").unlink()
            result = physical_result(folder, original_result)
            actual = result["physical_checks"]["maneuver"]["status"]
            if actual != expected or result["maneuver_completed"] != (expected == "met"):
                raise AssertionError(f"{kind}/{label}: expected {expected}, got {actual}")
            if expected == "met" and not result["realized_observables"]:
                raise AssertionError("complete crossing lacks measured observables")
            destination = ROOT / "cases" / kind / f"physical-{label}.json"
            if kind == "precedence":
                destination = ROOT / f"physical-{label}.json"
            write(destination, result)
            recorded.append({"kind": label, "result": str(destination.relative_to(ROOT)),
                             "result_sha256": sha(destination), "status": actual})
            print(kind, label, actual)
        complete = case_root / "complete_motion"
        seal = seal_capture(complete, frames=9,
                            restoration={"restored": True,
                                         "settings_readback": "CPU lifecycle protocol fixture"},
                            errors=[], encoder_exit_codes={"diagnostic": 0})
        exited = record_native_exit(complete)
        released = acknowledge_owner_release(complete,
                                             complete / "owner-release.json", True)
        stage = case_root / "saved_stage"
        stage.mkdir()
        copy_sources(complete, stage)
        if exited["capture_seal_sha256"] != sha(complete / "capture-seal.json") or \
                released["native_exit_sha256"] != sha(complete / "native-exit.json"):
            raise AssertionError("crossing lifecycle hashes differ")
        receipts.append({"case_id": ROOT.name + "__" + kind,
                         "construction_sha256": sha(origin / "construction.json"),
                         "fixtures": recorded, "lifecycle_events": seal["events"] +
                         ["native_exit", "owner_released", "saved_processing_started"],
                         "diagnostic_fixture": True,
                         "physical_acceptance_claimed": False})
    write(ROOT / "physical-outcome-diagnostic-proof.json", {
        "format": "c125714-physical-outcome-diagnostic-proof", "cases": receipts,
        "source_root": str(source.relative_to(REPO)),
        "scope": "Original-shaped synthetic source and lifecycle protocol; no Native or legal acceptance"})


if __name__ == "__main__":
    main()
