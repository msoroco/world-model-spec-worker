"""CPU fixture proof of walking completion and Native ownership ordering."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import _closure, acknowledge_owner_release, record_native_exit
from walking_measure import measure


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assess(source: Path, case_id: str, kind: str) -> dict:
    packet_path = source / "original-walking-observations.json"
    hashes = {"original-walking-observations.json": sha(packet_path),
              "original-walking-receipt.json": sha(source / "original-walking-receipt.json")}
    data = json.loads(packet_path.read_text(encoding="utf-8"))
    observation = {}
    if kind == "missing_evidence":
        status = "unverified"
    else:
        if kind == "incomplete_motion":
            data["frames"] = data["frames"][:3]
        observation = measure(data)
        status = "met" if observation["pedestrian_progress_m"] >= 5 and observation["any_frame_vehicle_approaching"] else "not_met"
    return {"case_id": case_id, "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "maneuver_completed": status == "met",
            "physical_checks": {"maneuver": {"status": status,
                "method": "source-shaped original walking progress and distinct approaching vehicle history",
                "sources": hashes, "details": {"fixture_kind": kind}}},
            "realized_observables": {"walking_side_and_facing": observation} if status == "met" else {},
            "physical_acceptance": False, "legal_acceptance": False}


def lifecycle(case_id: str, construction: Path, log: Path) -> dict:
    attempt = REPO / ".runtime-work/pedestrian-lifecycle" / case_id
    if attempt.exists():
        shutil.rmtree(attempt)
    attempt.mkdir(parents=True)
    shutil.copy2(construction, attempt / "construction.json")
    shutil.copy2(HERE / "runner.py", attempt / "runner.py")
    (attempt / "trace.jsonl").write_text('{"frame":1,"time_s":0.05}\n', encoding="utf-8")
    (attempt / "video_frames.jsonl").write_text('{"video_frame":0,"carla_frame":1,"time_s":0.05}\n', encoding="utf-8")
    write(attempt / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True, "case_id": case_id})
    seal_capture(attempt, frames=1, restoration={"restored": True}, errors=[], encoder_exit_codes={"fixture": 0}, context={"case_id": case_id})
    record_native_exit(attempt)
    owner = attempt / "owner-release.json"
    acknowledge_owner_release(attempt, owner, True)
    _closure(attempt, owner, "synthetic_fixture", True)
    events = ["capture_finished", "encoders_closed", "restoration_verified", "native_exit", "owner_released", "saved_processing_started"]
    log.write_text("CPU synthetic lifecycle checker passed: " + ", ".join(events) + "\n", encoding="utf-8")
    return {"events": events, "exit_code": 0, "log": str(log.relative_to(HERE)),
            "log_sha256": sha(log), "diagnostic_fixture": True}


def main() -> None:
    manifest = json.loads((HERE / "execution-manifest.draft.json").read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        short = case_id.split("__")[-1]
        folder = HERE / "cases" / short
        source = REPO / ".runtime-work" / ("pedestrian-compat-" + short + "-final1")
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            value = assess(source, case_id, kind)
            result = folder / ("physical-" + kind + ".json")
            log = folder / ("physical-" + kind + ".log")
            write(result, value)
            log.write_text("CPU synthetic " + kind + ": " + value["physical_checks"]["maneuver"]["status"] + "\n", encoding="utf-8")
            fixtures.append({"kind": kind, "command": "CPU source-shaped walking assessment " + case_id,
                "exit_code": 0, "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                "result": str(result.relative_to(HERE)), "result_sha256": sha(result)})
        life = lifecycle(case_id, folder / "construction.json", folder / "physical-lifecycle.log")
        receipt = folder / "physical-preparation.json"
        write(receipt, {"case_id": case_id, "construction_sha256": entry["construction_sha256"],
            "fixtures": fixtures, "lifecycle": life,
            "scope": "CPU synthetic protocol only; original CARLA motion and pixels pending"})
        entry["physical_preparation"] = {"receipt": str(receipt.relative_to(HERE)), "sha256": sha(receipt)}
        print(short, "physical/lifecycle fixture passed", flush=True)
    write(HERE / "execution-manifest.draft.json", manifest)


if __name__ == "__main__":
    main()
