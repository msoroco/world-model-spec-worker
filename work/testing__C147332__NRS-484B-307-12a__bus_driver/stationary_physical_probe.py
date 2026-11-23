"""Three source-bound CPU outcomes for the green-arrow stationary bus case."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from stationary_hold import SOURCES, audit


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def rows(path, values):
    Path(path).write_text("".join(json.dumps(value, allow_nan=False) + "\n"
                                  for value in values))


def make_fixture(folder, config, construction, kind):
    folder.mkdir()
    write(folder / "config.json", config)
    write(folder / "construction.json", construction)
    (folder / "runner.py").write_text(next(item["content"] for item in construction["files"]
                                            if item["path"] == "runner.py"))
    write(folder / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "physical_acceptance_claimed": False})
    bodies, traces, controls, frames = [], [], [], []
    for index in range(360):
        frame = 100 + index
        time = round(index / 20, 2)
        moving = kind == "incomplete_motion" and index >= 180
        x = 45 + (index - 179) * .1 if moving else 45
        body = [[x - 5, -2.8], [x + 5, -2.8],
                [x + 5, -.8], [x - 5, -.8]]
        bodies.append({"frame": frame, "elapsed_seconds": time, "bus_actor_id": 7,
                       "bus_footprint": body})
        traces.append({"frame": frame, "time_s": time, "position_m": [x, -1.8, 0],
                       "speed_mps": 2 if moving else 0})
        controls.append({"frame": frame, "elapsed_seconds": time,
                         "requested_control": {"brake": 0 if moving else 1,
                                               "throttle": .4 if moving else 0,
                                               "steer": 0}})
        frames.append({"video_frame": index, "carla_frame": frame, "time_s": time})
    for name, stream in zip(SOURCES, (bodies, traces, controls, frames)):
        if kind != "missing_evidence" or name != "controller-history.jsonl":
            rows(folder / name, stream)
    acquisition = {name: sha(folder / name) for name in SOURCES
                   if (folder / name).is_file()}
    write(folder / "acquisition.json", acquisition)
    return acquisition


def outcome(folder, acquisition, kind):
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    measured = None
    try:
        measured = audit(folder)
    except ValueError as error:
        reason = str(error)
        if kind == "incomplete_motion" and "stationary measured speed exceeded bound" not in reason:
            raise
        if kind == "missing_evidence" and "controller-history.jsonl" not in reason:
            raise
    else:
        if kind != "complete_motion":
            raise AssertionError("stationary hold accepted an incomplete fixture")
        reason = None
    result = {
        "physical_checks": {"maneuver": {
            "status": expected,
            "method": "original full-body, speed, brake and frame/time joined stationary_hold.audit",
            "sources": acquisition,
            "details": measured if measured else {"rejection": reason,
                                                 "sampled_frames": 360},
            "legal_verdict_claimed": False,
            "physical_causation_claimed": False}},
        "maneuver_completed": expected == "met",
        "realized_observables": ({"stationary_body_drift_m": {
            "value": measured["largest_body_drift_m"], "unit": "m",
            "frames": measured["frames"], "source_hashes": measured["source_hashes"]}}
                                 if measured else {}),
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "physical_acceptance_claimed": False,
        "scope": "CPU source protocol only; no Native capture or legal acceptance"}
    if result["physical_checks"]["maneuver"]["status"] != expected:
        raise AssertionError("stationary outcome mismatch")
    write(ROOT / f"physical-green_selected_stand-{kind}.json", result)
    print(kind, expected, reason if reason else measured["frames"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not output_root.is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("runtime output root must be under .runtime-work")
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
        acknowledge_owner_release, copy_sources)

    root = Path(args.output).resolve()
    if not root.is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("fixture output must be under .runtime-work")
    root.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    entry = next(item for item in manifest["cases"]
                 if item["case_id"].endswith("__green_selected_stand"))
    construction = json.loads((ROOT / entry["construction"]).read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        folder = root / kind
        acquisition = make_fixture(folder, config, construction, kind)
        outcome(folder, acquisition, kind)
    complete = root / "complete_motion"
    seal = seal_capture(complete, frames=360, restoration={
        "restored": True, "settings_readback": "CPU lifecycle protocol fixture"},
        errors=[], encoder_exit_codes={"diagnostic": 0})
    exited = record_native_exit(complete)
    released = acknowledge_owner_release(complete, complete / "owner-release.json", True)
    stage = root / "saved_stage"
    stage.mkdir()
    copy_sources(complete, stage)
    if exited["capture_seal_sha256"] != sha(complete / "capture-seal.json") or \
            released["native_exit_sha256"] != sha(complete / "native-exit.json"):
        raise AssertionError("lifecycle hash binding failed")
    print("lifecycle", *seal["events"], "native_exit", "owner_released",
          "saved_processing_started")
    print("diagnostic_only", True)


if __name__ == "__main__":
    main()
