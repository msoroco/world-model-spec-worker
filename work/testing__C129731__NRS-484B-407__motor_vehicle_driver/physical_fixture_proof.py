"""CPU exercise of the pinned turn-completion and ownership lifecycle checkers."""
import argparse
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
from worker_exchange.common import sha


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def run(manifest, case_id, kind, output, saved=None):
    manifest, output = Path(manifest).resolve(), Path(output).resolve()
    folder = manifest.parent
    entry = next(e for e in read(manifest)["cases"] if e["case_id"] == case_id)
    construction = read(folder / entry["construction"])
    config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    recipe = read(ROOT / entry["fixture_recipe"])
    sources = {item["path"]: ROOT / item["source"] for item in recipe["sources"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c129731-physical-") as temp:
        stage = Path(temp)
        write(stage / "config.json", config)
        for name in ("trace.jsonl", "video_frames.jsonl", "turn_history.jsonl", "curve_context.json"):
            if name not in sources or sha(sources[name]) != next(s["sha256"] for s in recipe["sources"] if s["path"] == name):
                raise ValueError("Exact fixture original source changed: " + name)
            (stage / name).write_bytes(sources[name].read_bytes())
        write(stage / "acquisition-provenance.json", {"provenance_kind": "native", "diagnostic_fixture": True,
                                                     "scope": "Source-shaped CPU classifier fixture only"})
        if kind == "lifecycle":
            if saved is None:
                raise ValueError("Current exact-case saved-processing receipt required")
            receipt = read(saved)
            if (receipt.get("format") != "worker-saved-processing" or receipt.get("passed") is not True or
                    receipt.get("recorded_only") is not True or
                    receipt["analysis_revision"]["construction_sha256"] != entry["construction_sha256"]):
                raise ValueError("Current selected saved-processing proof required")
            write(stage / "construction.json", construction)
            (stage / "runner.py").write_text(next(f["content"] for f in construction["files"] if f["path"] == "runner.py"))
            resource = io.StringIO("diagnostic resource")
            resource.close()
            if not resource.closed:
                raise ValueError("Capture owner not released")
            seal = seal_capture(stage, frames=1100, restoration={"restored": True, "fixture_only": True},
                                errors=[], encoder_exit_codes={"diagnostic_encoder": 0})
            exited = record_native_exit(stage)
            released = acknowledge_owner_release(stage, stage / "owner-release.json", True)
            events = seal["events"] + [exited["event"], released["event"], receipt["events"][0]]
            expected = ["capture_finished", "encoders_closed", "restoration_verified", "native_exit",
                        "owner_released", "saved_processing_started"]
            if events != expected:
                raise ValueError("Saved processing began before owner release")
            report = {"events": events, "diagnostic_fixture": True, "saved_processing_receipt_sha256": sha(saved),
                      "capture_seal_sha256": sha(stage / "capture-seal.json"),
                      "native_exit_sha256": sha(stage / "native-exit.json"),
                      "owner_release_sha256": sha(stage / "owner-release.json")}
        else:
            if kind == "incomplete_motion":
                turns = [json.loads(line) for line in (stage / "turn_history.jsonl").read_text().splitlines()]
                for row in turns:
                    row["heading_deg"] = turns[0]["heading_deg"]
                (stage / "turn_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in turns))
            elif kind == "missing_evidence":
                (stage / "turn_history.jsonl").unlink()
            report = physical_result(stage, {"target_checks": [], "realized_observables": {},
                                             "setup_confirmed": False, "behavior_attempted": False,
                                             "maneuver_completed": False})
            expected = {"complete_motion": "met", "incomplete_motion": "not_met", "missing_evidence": "unverified"}[kind]
            if (report["physical_checks"]["maneuver"]["status"] != expected or
                    report["diagnostic_fixture"] is not True or report["physical_acceptance_claimed"] is not False):
                raise ValueError("Pinned turn checker did not return expected diagnostic state")
        write(output, report)
        print(json.dumps({"case_id": case_id, "fixture": kind, "result": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--saved")
    args = parser.parse_args()
    run(args.manifest, args.case, args.kind, args.output, args.saved)
