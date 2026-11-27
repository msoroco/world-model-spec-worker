"""Exercise the frozen physical checker and capture closure with CPU fixtures.

These fixtures test measurement and ordering only. They do not assert that any
selected Native scene moved, was seen, or met a legal standard.
"""

import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "physical-fixtures-v3"
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.native_output import assess_physical, seal_capture
from scenario_pipeline.worker_exchange.saved_processing import (
    _closure, acknowledge_owner_release, record_native_exit)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def log(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n")


def fixture(case, kind, config):
    suffix = case.rsplit("__", 1)[-1]
    attempt = SCRATCH / suffix / kind
    attempt.mkdir(parents=True, exist_ok=True)
    write(attempt / "config.json", config)
    times = (0.0, 1.0, 2.0)
    native = (2000, 2001, 2002)
    (attempt / "video_frames.jsonl").write_text("".join(
        json.dumps({"video_frame": i, "carla_frame": frame,
                    "native_frame": frame, "time_s": times[i]}) + "\n"
        for i, frame in enumerate(native)))
    if kind != "missing_evidence":
        x_values = (0.0, 80.0, 120.0) if kind == "complete_motion" else (0.0, 0.5, 1.0)
        (attempt / "trace.jsonl").write_text("".join(
            json.dumps({"frame": frame, "time_s": times[i],
                        "position_m": [x_values[i], 0.0, 1.0]}) + "\n"
            for i, frame in enumerate(native)))
    assessed = assess_physical(attempt, config)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    actual = assessed["physical_checks"]["maneuver"]["status"]
    if actual != expected:
        raise AssertionError(f"{case} {kind}: {actual} != {expected}")
    result = {"case_id": case, "physical_checks": assessed["physical_checks"],
              "maneuver_completed": actual == "met",
              "realized_observables": assessed["realized_observables"],
              "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
              "legal_verdict_claimed": False}
    evidence = ROOT / "physical" / suffix
    result_path = evidence / (kind + "-result.json")
    log_path = evidence / (kind + ".log")
    write(result_path, result)
    log(log_path, f"{case} {kind}: physical maneuver={actual}; original-source-shaped diagnostic fixture only")
    return {"kind": kind,
            "command": f"SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c111603-physical .venv-cpu/bin/python -B {Path(__file__).relative_to(REPO)} --case {case} --kind {kind}",
            "exit_code": 0, "log": str(log_path.relative_to(ROOT)),
            "log_sha256": sha(log_path), "result": str(result_path.relative_to(ROOT)),
            "result_sha256": sha(result_path)}


def lifecycle(case, construction_path):
    suffix = case.rsplit("__", 1)[-1]
    attempt = SCRATCH / suffix / "lifecycle"
    attempt.mkdir(parents=True, exist_ok=True)
    (attempt / "trace.jsonl").write_text('{"frame":2000,"time_s":0,"position_m":[0,0,0]}\n')
    (attempt / "video_frames.jsonl").write_text('{"video_frame":0,"carla_frame":2000,"native_frame":2000,"time_s":0}\n')
    (attempt / "construction.json").write_bytes(construction_path.read_bytes())
    (attempt / "runner.py").write_text("# Synthetic lifecycle fixture; no Native process launched.\n")
    write(attempt / "acquisition-provenance.json",
          {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    seal = seal_capture(attempt, frames=1, restoration={"restored": True},
                        errors=[], encoder_exit_codes={"overview": 0})
    if seal["events"] != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise AssertionError("Capture seal ordering changed")
    exit_receipt = record_native_exit(attempt)
    if exit_receipt["event"] != "native_exit":
        raise AssertionError("Native exit missing")
    release_path = attempt / "owner-release.json"
    acknowledge_owner_release(attempt, release_path, True)
    _closure(attempt, release_path, "native", False)
    try:
        _closure(attempt, None, "native", False)
    except ValueError as exc:
        if "owner-release" not in str(exc):
            raise
    else:
        raise AssertionError("Native saved processing accepted absent owner release")
    evidence = ROOT / "physical" / suffix / "lifecycle.log"
    log(evidence, f"{case}: capture seal, encoder closure, restoration, Native exit, owner release verified; absent release rejected; saved processing may start")
    return {"events": ["capture_finished", "encoders_closed", "restoration_verified",
                       "native_exit", "owner_released", "saved_processing_started"],
            "exit_code": 0, "log": str(evidence.relative_to(ROOT)),
            "log_sha256": sha(evidence)}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--kind")
    args = parser.parse_args()
    index = json.loads((ROOT / "selected-preflight-manifest.json").read_text())
    cases = [row for row in index["cases"] if not args.case or row["case_id"] == args.case]
    for row in cases:
        case = row["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        config = json.loads((ROOT / "cases" / suffix / "config.json").read_text())
        kinds = [args.kind] if args.kind else ["complete_motion", "incomplete_motion", "missing_evidence"]
        fixtures = [fixture(case, kind, config) for kind in kinds]
        if args.kind:
            print(json.dumps({"case": case, "kind": args.kind, "passed": True}))
            continue
        life = lifecycle(case, ROOT / row["construction"])
        receipt = {"format": "worker-c111603-physical-preparation-v1",
                   "case_id": case, "construction_sha256": row["construction_sha256"],
                   "fixtures": fixtures, "lifecycle": life,
                   "scope": "synthetic CPU checker and owner-release protocol only"}
        path = ROOT / "physical" / suffix / "receipt.json"
        staged = SCRATCH / suffix / "receipt.json"
        write(staged, receipt)
        os.replace(staged, path)
        print(json.dumps({"case": suffix, "receipt_sha256": sha(path)}), flush=True)


if __name__ == "__main__":
    main()
