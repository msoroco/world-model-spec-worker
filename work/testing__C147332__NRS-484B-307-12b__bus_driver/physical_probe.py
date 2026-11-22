"""CPU motion and lifecycle probes for the three moving red-X bus cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_fixture(folder, config, construction, kind):
    folder.mkdir()
    write(folder / "config.json", config)
    write(folder / "construction.json", construction)
    (folder / "runner.py").write_text(next(item["content"] for item in construction["files"]
                                            if item["path"] == "runner.py"))
    write(folder / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
          "diagnostic_fixture": True, "physical_acceptance_claimed": False})
    if kind == "missing_evidence":
        return
    rows, mapping = [], []
    for index in range(9):
        frame, time = 100 + index, index / 20
        x = index * (10 if kind == "complete_motion" else .05)
        rows.append({"frame": frame, "time_s": time, "position_m": [x, -1.8, 0],
                     "heading_deg": 0, "speed_mps": 8})
        mapping.append({"video_frame": index, "carla_frame": frame, "time_s": time})
    (folder / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    (folder / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in mapping))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
        acknowledge_owner_release, copy_sources)

    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    kind = args.case.rsplit("__", 1)[-1]
    if kind == "red_lane_stand":
        raise ValueError("stationary physical criterion needs a separate source-bound proof")
    construction = json.loads((ROOT / entry["construction"]).read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    for outcome, expected in (("complete_motion", "met"),
                              ("incomplete_motion", "not_met"),
                              ("missing_evidence", "unverified")):
        folder = root / outcome
        make_fixture(folder, config, construction, outcome)
        result = physical_result(folder, {"target_checks": [{"target": "diagnostic bus progress",
            "requested": True, "measured": outcome == "complete_motion",
            "method": "source-bound CPU trace rows", "tolerance": 0,
            "matched": outcome == "complete_motion", "physical_cause_confirmed": False,
            "cause_evidence": "synthetic diagnostic only"}]})
        actual = result["physical_checks"]["maneuver"]["status"]
        if actual != expected or result["maneuver_completed"] != (expected == "met"):
            raise ValueError("physical outcome mismatch: " + outcome + " " + actual)
        if expected == "met" and not result["realized_observables"]:
            raise ValueError("complete outcome lacks measured original-shaped trace")
        write(ROOT / f"physical-{kind}-{outcome}.json", result)
        print(outcome, actual)
    complete = root / "complete_motion"
    seal = seal_capture(complete, frames=9, restoration={"restored": True,
        "settings_readback": "CPU lifecycle protocol fixture"}, errors=[],
        encoder_exit_codes={"diagnostic": 0})
    exited = record_native_exit(complete)
    released = acknowledge_owner_release(complete, complete / "owner-release.json", True)
    stage = root / "saved_stage"
    stage.mkdir()
    copy_sources(complete, stage)
    if exited["capture_seal_sha256"] != sha(complete / "capture-seal.json") or \
            released["native_exit_sha256"] != sha(complete / "native-exit.json"):
        raise ValueError("lifecycle hash binding failed")
    print("lifecycle", *seal["events"], "native_exit", "owner_released",
          "saved_processing_started")
    print("diagnostic_only", True)


if __name__ == "__main__":
    main()
