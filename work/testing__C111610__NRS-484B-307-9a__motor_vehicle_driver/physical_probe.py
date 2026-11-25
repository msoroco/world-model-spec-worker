"""Synthetic CPU proof of turn/progress outcomes and capture ownership order."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(path, config, construction, kind):
    path.mkdir()
    write(path / "config.json", config)
    write(path / "construction.json", construction)
    (path / "runner.py").write_text(next(f["content"] for f in construction["files"]
                                         if f["path"] == "runner.py"))
    write(path / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    if kind == "missing_evidence":
        return
    complete = kind == "complete_motion"
    rows, trace, mapping = [], [], []
    for index in range(9):
        frame, time_s = 200 + index, index / 20
        x = index if complete else index / 20
        heading = index * 90 / 8 if complete and config["case_suffix"] != "wrong_movement" else 0
        vertices = [[x + dx, dy, 0] for dx, dy in
                    ((-1, -0.5), (-1, 0.5), (1, 0.5), (1, -0.5))]
        rows.append({"frame": frame, "time_s": time_s,
                     "body_vertices_m": vertices, "heading_deg": heading})
        trace.append({"frame": frame, "time_s": time_s,
                      "position_m": [x, 0, 0], "heading_deg": heading})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": time_s})
    for name, values in (("body_history.jsonl", rows), ("trace.jsonl", trace),
                         ("video_frames.jsonl", mapping)):
        (path / name).write_text("".join(json.dumps(row) + "\n" for row in values))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
        acknowledge_owner_release, copy_sources)
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    entry = next(row for row in manifest["cases"] if row["case_id"] == args.case)
    construction = json.loads((ROOT / entry["construction"]).read_text())
    config = json.loads(next(row["content"] for row in construction["files"]
                             if row["path"] == "config.json"))
    suffix = args.case.rsplit("__", 1)[-1]
    scratch = Path(args.output).resolve()
    scratch.mkdir(parents=True, exist_ok=False)
    for kind, expected in (("complete_motion", "met"),
                           ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        folder = scratch / kind
        fixture(folder, config, construction, kind)
        result = physical_result(folder, {"target_checks": [{
            "target": "original turn or progress", "requested": True,
            "measured": kind == "complete_motion", "method": "CPU source-shaped body history",
            "tolerance": 0, "matched": kind == "complete_motion",
            "physical_cause_confirmed": False,
            "cause_evidence": "synthetic diagnostic motion only"}]})
        if (result["physical_checks"]["maneuver"]["status"] != expected or
                result["maneuver_completed"] != (expected == "met")):
            raise ValueError("physical outcome mismatch: " + kind)
        write(ROOT / ("physical-" + suffix + "-" + kind + ".json"), result)
        print(kind, expected)
    complete = scratch / "complete_motion"
    seal = seal_capture(complete, frames=9,
        restoration={"restored": True, "settings_readback": "CPU protocol fixture"},
        errors=[], encoder_exit_codes={"diagnostic": 0})
    exit_receipt = record_native_exit(complete)
    owner = acknowledge_owner_release(complete, complete / "owner-release.json", True)
    stage = scratch / "saved_stage"
    stage.mkdir()
    copy_sources(complete, stage)
    if (exit_receipt["capture_seal_sha256"] != sha(complete / "capture-seal.json") or
            owner["native_exit_sha256"] != sha(complete / "native-exit.json")):
        raise ValueError("lifecycle source binding failed")
    print("lifecycle", *seal["events"], "native_exit", "owner_released",
          "saved_processing_started")


if __name__ == "__main__":
    main()
