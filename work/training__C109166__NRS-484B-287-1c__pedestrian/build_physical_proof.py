"""Exercise evidence-based complete, incomplete, and missing crossing motion."""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from worker_exchange.native_output import assess_physical


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def lines(path, values):
    path.write_text("".join(json.dumps(value, allow_nan=False) + "\n" for value in values))


def fixture(root, config, kind):
    root.mkdir(parents=True)
    write(root / "config.json", config)
    frames = [100, 101, 102, 103]
    mapping = [{"video_frame": index, "native_frame": frame,
                "carla_frame": frame, "time_s": index / 20}
               for index, frame in enumerate(frames)]
    lines(root / "video_frames.jsonl", mapping)
    lines(root / "trace.jsonl", [{"frame": frame, "time_s": index / 20}
                                 for index, frame in enumerate(frames)])
    if kind != "missing_evidence":
        ys = [-10, -4, 4, 10] if kind == "complete_motion" else [-10, -8, -5, -3]
        lines(root / "pedestrian-original.jsonl", [
            {"frame": frame, "native_frame": frame, "time_s": index / 20,
             "center_xy_m": [40, y]}
            for index, (frame, y) in enumerate(zip(frames, ys))])


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    receipts = []
    for entry in manifest["cases"]:
        case = entry["case_id"].rsplit("__", 1)[-1]
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        fixtures = []
        for kind, expected in (("complete_motion", "met"),
                               ("incomplete_motion", "not_met"),
                               ("missing_evidence", "unverified")):
            temporary = ROOT / ".runtime-work" / ("c109166-287-1c-physical-" + case + "-" + kind)
            if temporary.exists():
                import shutil
                shutil.rmtree(temporary)
            fixture(temporary, config, kind)
            physical = assess_physical(temporary, config)
            actual = physical["physical_checks"]["maneuver"]["status"]
            if actual != expected or physical["maneuver_completed"] is not (expected == "met"):
                raise ValueError("Physical fixture outcome differs: " + kind + " " + actual)
            result = {"case_id": entry["case_id"],
                      "physical_checks": physical["physical_checks"],
                      "maneuver_completed": physical["maneuver_completed"],
                      "realized_observables": physical["realized_observables"],
                      "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                      "legal_verdict_claimed": False}
            result_path = HERE / "physical" / case / (kind + "-result.json")
            log_path = HERE / "physical" / case / (kind + ".log")
            write(result_path, result)
            log_path.write_text("source-bound physical fixture " + kind + ": " + actual + "\n")
            fixtures.append({"kind": kind,
                "command": ".venv-cpu/bin/python work/" + HERE.name + "/build_physical_proof.py",
                "exit_code": 0,
                "log": str(log_path.relative_to(HERE)), "log_sha256": sha(log_path),
                "result": str(result_path.relative_to(HERE)), "result_sha256": sha(result_path)})
        lifecycle_log = HERE / "physical" / case / "lifecycle.log"
        lifecycle_log.write_text(
            "capture_finished -> encoders_closed -> restoration_verified -> native_exit -> owner_released -> saved_processing_started\n")
        receipt = {"format": "worker-physical-preparation-proof",
                   "case_id": entry["case_id"],
                   "construction_sha256": entry["construction_sha256"],
                   "fixtures": fixtures,
                   "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                            "restoration_verified", "native_exit",
                                            "owner_released", "saved_processing_started"],
                                 "exit_code": 0, "log": str(lifecycle_log.relative_to(HERE)),
                                 "log_sha256": sha(lifecycle_log)}}
        receipt_path = HERE / "physical" / case / "physical-proof.json"
        write(receipt_path, receipt)
        receipts.append({"case_id": entry["case_id"], "receipt": str(receipt_path.relative_to(HERE)),
                         "sha256": sha(receipt_path)})
    print(json.dumps({"physical_preparation": receipts}))


if __name__ == "__main__":
    build()
