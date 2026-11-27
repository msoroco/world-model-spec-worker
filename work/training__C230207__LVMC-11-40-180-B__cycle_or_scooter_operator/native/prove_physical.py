"""Synthetic 600-frame signed-route outcomes and saved lifecycle order."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from prove_signed_access_measure import write_case
from signed_access_measure import derive


HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def prove(case):
    suffix = case.rsplit("__", 1)[-1]
    if case != HERE.name + "__" + suffix or suffix not in ("witness_1", "witness_2"):
        raise ValueError("Wrong exact signed-road case")
    construction = HERE / ("construction.json" if suffix == "witness_1" else
                           "cases/" + suffix + "/construction.json")
    output = HERE / "physical" / suffix
    output.mkdir(parents=True, exist_ok=True)
    fixtures = []
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work",
                                     prefix="c230207-physical-") as temporary:
        root = Path(temporary)
        for kind, expected in (("complete_motion", "met"),
                               ("incomplete_motion", "not_met"),
                               ("missing_evidence", "unverified")):
            folder = root / kind
            write_case(folder, suffix == "witness_2")
            if kind == "incomplete_motion":
                p = folder / "raw-frames.json"
                rows = json.loads(p.read_text())
                rows[200]["riding_machine"] = False
                save(p, rows)
            if kind == "missing_evidence":
                (folder / "setup.json").unlink()
            try:
                measured = derive(folder)
                status = "met" if measured["riding_frames"] == 600 and (
                    measured["inside_governed_segment_frames"] == (0 if suffix == "witness_1" else 400)) else "not_met"
                source_hashes = {name: digest(folder / name) for name in
                                 ("setup.json", "raw-frames.json")}
            except (ValueError, FileNotFoundError) as error:
                if kind == "complete_motion":
                    raise
                status = "not_met" if kind == "incomplete_motion" else "unverified"
                measured = {"error": str(error)}
                source_hashes = {"setup.json": digest(folder / "setup.json") if
                                 (folder / "setup.json").exists() else "missing",
                                 "raw-frames.json": digest(folder / "raw-frames.json")}
            if status != expected:
                raise ValueError("Synthetic physical status differs: " + kind)
            result = {"case_id": case, "physical_checks": {"maneuver": {
                "status": status, "method": "600 source-joined synthetic riding frames",
                "sources": source_hashes}}, "maneuver_completed": status == "met",
                "realized_observables": ({"signed_roadway_riding_frames":
                                          measured["inside_governed_segment_frames"]}
                                         if status == "met" else {}),
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "original_native_executed": False,
                "physical_or_legal_acceptance": False}
            result_path = output / (kind + "-result.json")
            log_path = output / (kind + ".log")
            save(result_path, result)
            save(log_path, {"kind": kind, "expected": expected,
                            "observed": status, "sources": source_hashes,
                            "measurement": measured, "diagnostic_only": True})
            fixtures.append({"kind": kind,
                "command": ".venv-cpu/bin/python work/" + HERE.name +
                           "/native/prove_physical.py --case " + case,
                "exit_code": 0, "log": str(log_path.relative_to(HERE)),
                "log_sha256": digest(log_path),
                "result": str(result_path.relative_to(HERE)),
                "result_sha256": digest(result_path)})
        life = root / "lifecycle"
        life.mkdir()
        save(life / "acquisition-provenance.json", {"diagnostic_fixture": True})
        (life / "construction.json").write_bytes(construction.read_bytes())
        (life / "runner.py").write_text("# Synthetic lifecycle protocol fixture\n")
        (life / "trace.jsonl").write_text('{"synthetic":true}\n')
        (life / "video_frames.jsonl").write_text('{"video_frame":0,"native_frame":1,"time_s":0.0}\n')
        seal = seal_capture(life, frames=600, restoration={"restored": True},
                            errors=[], encoder_exit_codes={name: 0 for name in
                            ("overview", "approach", "reference_corner", "driver_reference")})
        exit_row = record_native_exit(life)
        owner = acknowledge_owner_release(life, life / "owner-release.json", True)
        events = seal["events"] + [exit_row["event"], owner["event"],
                                   "saved_processing_started"]
        required = ["capture_finished", "encoders_closed", "restoration_verified",
                    "native_exit", "owner_released", "saved_processing_started"]
        if events != required:
            raise ValueError("Saved work began before Native closure")
        life_log = output / "lifecycle.log"
        save(life_log, {"events": events, "diagnostic_only": True})
    proof = output / "physical-preparation.json"
    save(proof, {"format": "c230207-signed-road-physical-cpu-proof-v1",
                 "case_id": case, "construction_sha256": digest(construction),
                 "fixtures": fixtures,
                 "lifecycle": {"events": required, "exit_code": 0,
                               "log": str(life_log.relative_to(HERE)),
                               "log_sha256": digest(life_log)},
                 "original_native_executed": False})
    print(json.dumps({"case_id": case, "sha256": digest(proof)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    prove(args.case)


if __name__ == "__main__":
    main()
