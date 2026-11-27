"""CPU-only physical and closure probes for the exact steady-red constructions.

The source fixture is diagnostic. These probes never assert a Native capture or
a legal outcome.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case, source, scratch, destination):
    repo = Path(__file__).resolve().parents[1].parent
    os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT", str(repo / ".runtime-work" / "c111331-physical-output"))
    sys.path.insert(0, str(repo / "runtime"))
    from scenario_pipeline.worker_exchange.native_output import physical_result, seal_capture
    from scenario_pipeline.worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

    source = Path(source).resolve()
    scratch = Path(scratch).resolve()
    destination = Path(destination).resolve()
    if repo / ".runtime-work" not in scratch.parents:
        raise ValueError("Physical fixture scratch must remain in .runtime-work")
    provenance = json.loads(source.joinpath("result.json").read_text())
    if provenance.get("provenance_kind") != "synthetic_fixture" or provenance.get("diagnostic_fixture") is not True:
        raise ValueError("Physical CPU proof requires synthetic source")
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    destination.mkdir(parents=True, exist_ok=True)
    names = ("config.json", "construction.json", "runner.py", "trace.jsonl",
             "video_frames.jsonl", "capture/evidence.jsonl")
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        root = scratch / kind
        root.mkdir()
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, target)
        (root / "acquisition-provenance.json").write_text(json.dumps({"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        if kind == "incomplete_motion":
            rows = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
            first_position = rows[0]["position_m"]
            for row in rows:
                row["position_m"] = first_position
            (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        if kind == "missing_evidence":
            (root / "trace.jsonl").unlink()
        result = physical_result(root, {"case_id": case, "target_checks": []})
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        status = result["physical_checks"]["maneuver"]["status"]
        if status != expected or result["maneuver_completed"] != (expected == "met"):
            raise AssertionError(f"{kind}: expected {expected}, got {status}")
        if kind == "complete_motion" and not result["realized_observables"]:
            raise AssertionError("Complete physical fixture lacks measured motion")
        result["physical_acceptance_claimed"] = False
        output = destination / f"{kind}.json"
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"kind": kind, "status": status, "result": str(output),
                          "result_sha256": digest(output), "diagnostic_fixture": True}))

    closure = scratch / "closure"
    closure.mkdir()
    for name in ("construction.json", "runner.py", "trace.jsonl", "video_frames.jsonl",
                 "config.json"):
        shutil.copy2(source / name, closure / name)
    (closure / "acquisition-provenance.json").write_text(json.dumps({"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
    seal_capture(closure, frames=480, restoration={"restored": True}, errors=[],
                 encoder_exit_codes={"overview": 0, "approach": 0,
                                     "reference_corner": 0, "driver_reference": 0})
    try:
        acknowledge_owner_release(closure, closure / "owner-release.json", True)
    except ValueError as error:
        if "Native process has not exited" not in str(error):
            raise
    else:
        raise AssertionError("Owner release accepted before Native exit")
    record_native_exit(closure)
    acknowledge_owner_release(closure, closure / "owner-release.json", True)
    _closure(closure, closure / "owner-release.json", "synthetic_fixture", True)
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    print(json.dumps({"lifecycle": events, "diagnostic_fixture": True,
                      "negative_owner_release_before_exit_rejected": True,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--destination", required=True)
    options = parser.parse_args()
    run(options.case, options.source, options.scratch, options.destination)
