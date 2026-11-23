"""Exercise the canonical physical classifier on source-bound CPU fixtures.

These are synthetic diagnostics, never evidence of a Native capture or a legal
determination. The classifier itself receives no fixture-kind hint.
"""

import argparse
import io
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
from worker_exchange.common import sha


def read(path):
    return json.loads(Path(path).read_text())


def exercise(entry, folder, kind, output):
    construction = read(folder / entry["construction"])
    config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    recipe = read(REPO / entry["fixture_recipe"])
    diagnostic = read(REPO / recipe["generator"]["source"])
    source = config["physical_completion"]["motion_source"]
    with tempfile.TemporaryDirectory(prefix="c412593-physical-") as name:
        stage = Path(name)
        (stage / "config.json").write_text(json.dumps(config) + "\n")
        for file in ("trace.jsonl", "video_frames.jsonl", source):
            (stage / file).write_text(diagnostic["files"][file])
        (stage / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "scope": "CPU classifier diagnostic; no physical acquisition"
        }) + "\n")
        if kind == "incomplete_motion":
            rows = [json.loads(line) for line in (stage / source).read_text().splitlines()]
            destination = config["physical_completion"]["destination_road"]
            start = rows[0][config["physical_completion"]["road_key"]]
            if start == destination:
                raise ValueError("Fixture starts on destination road")
            for row in rows:
                row[config["physical_completion"]["road_key"]] = start
            (stage / source).write_text("".join(json.dumps(row) + "\n" for row in rows))
        elif kind == "missing_evidence":
            (stage / source).unlink()
        result = physical_result(stage, {
            "target_checks": [], "realized_observables": {},
            "setup_confirmed": False, "behavior_attempted": False,
            "maneuver_completed": False,
        })
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        actual = result["physical_checks"]["maneuver"]["status"]
        if actual != expected or result["diagnostic_fixture"] is not True:
            raise ValueError(f"Physical classifier returned {actual}; expected {expected}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"case_id": entry["case_id"], "fixture": kind,
                          "status": actual, "sources": result["physical_checks"]["maneuver"]["sources"]}))


def lifecycle(entry, folder, saved_path, output):
    saved = read(saved_path)
    if (saved.get("format") != "worker-saved-processing" or saved.get("passed") is not True
            or saved.get("recorded_only") is not True
            or saved["analysis_revision"]["construction_sha256"] != entry["construction_sha256"]):
        raise ValueError("Exact selected saved-only proof missing")
    construction = read(folder / entry["construction"])
    with tempfile.TemporaryDirectory(prefix="c412593-lifecycle-") as name:
        stage = Path(name)
        (stage / "construction.json").write_text(json.dumps(construction) + "\n")
        (stage / "runner.py").write_text(next(f["content"] for f in construction["files"] if f["path"] == "runner.py"))
        (stage / "trace.jsonl").write_text('{"frame":1,"time_s":0.05}\n')
        (stage / "video_frames.jsonl").write_text('{"video_frame":0,"carla_frame":1,"time_s":0.05}\n')
        (stage / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "scope": "Synthetic lifecycle CPU fixture only"}) + "\n")
        owner = io.StringIO("fixture resource")
        owner.close()
        if not owner.closed:
            raise ValueError("Fixture resource owner was not released")
        seal = seal_capture(stage, frames=1, restoration={"restored": True, "fixture_only": True},
                            errors=[], encoder_exit_codes={"fixture_encoder": 0},
                            context={"diagnostic_fixture": True})
        exited = record_native_exit(stage)
        released = acknowledge_owner_release(stage, stage / "owner-release.json", True)
        if (exited["capture_seal_sha256"] != sha(stage / "capture-seal.json")
                or released["native_exit_sha256"] != sha(stage / "native-exit.json")):
            raise ValueError("Lifecycle digest join failed")
        events = seal["events"] + [exited["event"], released["event"], saved["events"][0]]
        expected = ["capture_finished", "encoders_closed", "restoration_verified",
                    "native_exit", "owner_released", "saved_processing_started"]
        if events != expected:
            raise ValueError("Lifecycle event ordering differs")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"events": events, "diagnostic_fixture": True,
                                      "saved_processing_receipt_sha256": sha(saved_path),
                                      "capture_seal_sha256": sha(stage / "capture-seal.json"),
                                      "native_exit_sha256": sha(stage / "native-exit.json"),
                                      "owner_release_sha256": sha(stage / "owner-release.json")}, indent=2) + "\n")
        print(json.dumps({"case_id": entry["case_id"], "events": events,
                          "diagnostic_fixture": True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--saved-receipt")
    args = parser.parse_args()
    manifest = Path(args.manifest).resolve()
    entry = next(e for e in read(manifest)["cases"] if e["case_id"] == args.case)
    if args.kind == "lifecycle":
        if not args.saved_receipt:
            raise ValueError("Lifecycle fixture requires saved receipt")
        lifecycle(entry, manifest.parent, Path(args.saved_receipt), Path(args.output))
    else:
        exercise(entry, manifest.parent, args.kind, Path(args.output))


if __name__ == "__main__":
    main()
