"""Source-shaped CPU motion and Native ownership protocol proof for C111125."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root, config, construction, kind):
    root.mkdir()
    write(root / "config.json", config)
    write(root / "construction.json", construction)
    (root / "runner.py").write_text(next(item["content"] for item in construction["files"]
                                            if item["path"] == "runner.py"), encoding="utf-8")
    write(root / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    if kind == "missing_evidence":
        return
    trace = []
    mapping = []
    for index in range(900):
        x = (30.0 if kind == "complete_motion" else 3.0) * index / 899
        trace.append({"frame": 1000 + index, "time_s": index / 20,
                      "position_m": [x, 0, 0], "speed_mps": 1})
        mapping.append({"video_frame": index, "carla_frame": 1000 + index,
                        "time_s": index / 20})
    (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace), encoding="utf-8")
    (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in mapping), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
    manifest = json.loads((HERE / "execution-manifest.json").read_text(encoding="utf-8"))
    entry = next((row for row in manifest["cases"] if row["case_id"] == args.case), None)
    if entry is None:
        raise ValueError("C111125 exact case missing")
    construction = json.loads((HERE / entry["construction"]).read_text(encoding="utf-8"))
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    results = {}
    for kind, expected in (("complete_motion", "met"), ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        folder = root / kind
        fixture(folder, config, construction, kind)
        value = physical_result(folder, {"target_checks": [{
            "target": "source-shaped straight route progress", "requested": True,
            "measured": kind == "complete_motion", "method": "synthetic route trace",
            "tolerance": 0, "matched": kind == "complete_motion",
            "physical_cause_confirmed": False,
            "cause_evidence": "diagnostic CPU fixture only"}]})
        if value["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("C111125 physical fixture expected " + expected)
        results[kind] = value
        print(kind, expected)
    complete = root / "complete_motion"
    sealed = seal_capture(complete, frames=900,
                          restoration={"restored": True, "settings_readback": "CPU protocol fixture"},
                          errors=[], encoder_exit_codes={"diagnostic": 0})
    native_exit = record_native_exit(complete)
    owner = acknowledge_owner_release(complete, complete / "owner-release.json", True)
    stage = root / "saved_stage"
    stage.mkdir()
    copy_sources(complete, stage)
    if native_exit["capture_seal_sha256"] != sha(complete / "capture-seal.json") or \
            owner["native_exit_sha256"] != sha(complete / "native-exit.json"):
        raise ValueError("Native lifecycle source binding failed")
    print("lifecycle", *sealed["events"], "native_exit", "owner_released", "saved_processing_started")
    write(root / "probe-summary.json", {
        "format": "worker-c111125-physical-probe", "case_id": args.case,
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "physical_acceptance_claimed": False,
        "outcomes": {kind: value["physical_checks"]["maneuver"]["status"]
                     for kind, value in results.items()},
        "lifecycle_events": sealed["events"] + ["native_exit", "owner_released", "saved_processing_started"]})


if __name__ == "__main__":
    main()
