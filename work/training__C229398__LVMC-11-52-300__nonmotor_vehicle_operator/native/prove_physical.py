"""Source-shaped CPU outcomes and canonical closure ordering; synthetic only."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release

from duration_policy import TARGETS, TOTAL_FRAMES, stop_frame
from selected_measurement import measure
from source_gate import FIELDS


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def build_sources(folder, suffix):
    case = HERE.name + "__" + suffix
    construction = HERE / ("construction.json" if suffix == "below_30" else
                           "cases/" + suffix + "/construction.json")
    parsed = json.loads(construction.read_text())
    config = json.loads(next(item["content"] for item in parsed["files"] if
                             item["path"] == "config.json"))
    write(folder / "config.json", config)
    (folder / "construction.json").write_bytes(construction.read_bytes())
    (folder / "runner.py").write_text("# Synthetic lifecycle fixture only\n")
    findings = {"transport_capability": True, "excluded_device": False,
                "self_propulsion": False, "responsible_person": "synthetic operator",
                "parking_purpose": "park", "active_loading_or_unloading": False,
                "street_public_access": True, "city_limits": True,
                "civil_clock": {"iana_timezone": "America/Los_Angeles",
                                "utc_start_ms": 1795425000000}}
    sources = {}
    for field in FIELDS:
        name = "synthetic-" + field + ".json"
        write(folder / name, {"synthetic_finding": findings[field]})
        sources[field] = {"path": name, "sha256": digest(folder / name),
                          "citation": "Synthetic CPU outcome fixture: " + field,
                          "source_kind": "synthetic_cpu"}
    write(folder / "review-source.json", {"format": "c229398-source-review-v1",
          "case_id": case, "source_kind": "synthetic_cpu", "findings": findings,
          "sources": sources})
    write(folder / "street-geometry.json", {"street_bounds_xy_m": [0, 100, -3.5, 3.5],
          "source_kind": "synthetic_cpu"})
    return construction


def write_frames(folder, suffix, kind):
    stop = stop_frame(HERE.name + "__" + suffix)
    if kind == "incomplete_motion":
        stop = TOTAL_FRAMES - 101
    with (folder / "native-actor-frames.jsonl").open("w") as actor, (
            folder / "video_frames.jsonl").open("w") as mapping, (
            folder / "trace.jsonl").open("w") as trace:
        for frame in range(TOTAL_FRAMES):
            native = 100 + frame
            velocity = 0.0 if frame >= stop else 1.5
            actor.write(json.dumps({"frame": frame, "native_frame": native,
                                    "center_xyz_m": [40.0, -1.75, 0.5],
                                    "velocity_xyz_mps": [velocity, 0.0, 0.0]}) + "\n")
            mapping.write(json.dumps({"video_frame": frame, "carla_frame": native,
                                      "native_frame": native, "time_s": frame / 20}) + "\n")
            trace.write(json.dumps({"frame": native, "time_s": frame / 20,
                                    "position_m": [40.0, -1.75, 0.5],
                                    "velocity_mps": [velocity, 0.0, 0.0]}) + "\n")


def prove_case(suffix):
    case = HERE.name + "__" + suffix
    directory = HERE / "physical" / suffix
    directory.mkdir(parents=True, exist_ok=True)
    fixtures = []
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work",
                                     prefix="c229398-physical-") as temporary:
        folder = Path(temporary)
        construction = build_sources(folder, suffix)
        for kind, expected in (("complete_motion", "met"),
                               ("incomplete_motion", "not_met"),
                               ("missing_evidence", "unverified")):
            write_frames(folder, suffix, kind)
            street = folder / "street-geometry.json"
            if kind == "missing_evidence":
                street.unlink()
            try:
                episode = measure(folder)
                observed = episode["longest_continuous_qualifying_ms"]
                target = round(TARGETS[suffix] * 1000)
                status = "met" if abs(observed - target) <= 50 else "not_met"
                source_hashes = episode["sources"]
            except ValueError as error:
                if kind != "missing_evidence" or "Missing required source: street-geometry.json" not in str(error):
                    raise
                observed = None
                status = "unverified"
                source_hashes = {"review-source.json": digest(folder / "review-source.json"),
                                 "native-actor-frames.jsonl": digest(folder / "native-actor-frames.jsonl"),
                                 "street-geometry.json": "missing"}
            if status != expected:
                raise ValueError("Synthetic physical outcome differs: " + kind)
            result = {"case_id": case, "physical_checks": {"maneuver": {
                "status": status, "method": "full-length synthetic source-joined parking meter",
                "sources": source_hashes}}, "maneuver_completed": status == "met",
                "realized_observables": ({"night_parking_duration_ms": observed} if status == "met" else {}),
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
            result_path = directory / (kind + "-result.json")
            log_path = directory / (kind + ".log")
            write(result_path, result)
            write(log_path, {"kind": kind, "expected": expected,
                             "observed_status": status, "observed_duration_ms": observed,
                             "source_hashes": source_hashes,
                             "scope": "full-length synthetic CPU fixture only"})
            fixtures.append({"kind": kind,
                "command": ".venv-cpu/bin/python work/" + HERE.name +
                           "/native/prove_physical.py --case " + case,
                "exit_code": 0, "log": str(log_path.relative_to(HERE)),
                "log_sha256": digest(log_path), "result": str(result_path.relative_to(HERE)),
                "result_sha256": digest(result_path)})
            if not street.exists():
                write(street, {"street_bounds_xy_m": [0, 100, -3.5, 3.5],
                      "source_kind": "synthetic_cpu"})
        write(folder / "acquisition-provenance.json", {"diagnostic_fixture": True})
        seal = seal_capture(folder, frames=TOTAL_FRAMES,
                            restoration={"restored": True}, errors=[],
                            encoder_exit_codes={"overview": 0, "approach": 0,
                                                "reference_corner": 0,
                                                "driver_reference": 0})
        exited = record_native_exit(folder)
        owner = acknowledge_owner_release(folder, folder / "owner-release.json", True)
        events = seal["events"] + [exited["event"], owner["event"],
                                   "saved_processing_started"]
        expected_events = ["capture_finished", "encoders_closed", "restoration_verified",
                           "native_exit", "owner_released", "saved_processing_started"]
        if events != expected_events:
            raise ValueError("Synthetic lifecycle order differs")
        lifecycle_log = directory / "lifecycle.log"
        write(lifecycle_log, {"events": events,
             "seal_sha256": digest(folder / "capture-seal.json"),
             "native_exit_sha256": digest(folder / "native-exit.json"),
             "owner_release_sha256": digest(folder / "owner-release.json"),
             "scope": "CPU protocol fixture; no Native owner acquired"})
    proof = directory / "physical-preparation.json"
    write(proof, {"format": "c229398-physical-preparation-cpu-proof-v1",
                  "case_id": case, "construction_sha256": digest(construction),
                  "fixtures": fixtures,
                  "lifecycle": {"events": expected_events, "exit_code": 0,
                                "log": str(lifecycle_log.relative_to(HERE)),
                                "log_sha256": digest(lifecycle_log)},
                  "original_native_executed": False})
    return {"case_id": case, "receipt": str(proof.relative_to(HERE)),
            "sha256": digest(proof)}


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--case":
        raise SystemExit("expected --case exact case ID")
    suffix = sys.argv[2].rsplit("__", 1)[-1]
    if sys.argv[2] != HERE.name + "__" + suffix or suffix not in TARGETS:
        raise SystemExit("wrong exact case")
    print(json.dumps(prove_case(suffix), indent=2))
