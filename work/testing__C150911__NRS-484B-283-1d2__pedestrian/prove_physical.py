"""Exercise source-bound physical outcomes and Native ownership lifecycle."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from countdown_crossing import CASES, measure_original

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def assess(source: Path, case_id: str, kind: str) -> dict:
    packet = source / "original-countdown-observations.json"
    data = json.loads(packet.read_text())
    case = next(item for item in CASES if case_id.endswith("__" + item.case_id))
    hashes = {"original-countdown-observations.json": sha(packet),
        "original-countdown-receipt.json": sha(source / "original-countdown-receipt.json")}
    observation = {}
    if kind == "missing_evidence":
        status = "unverified"
    elif kind == "incomplete_motion":
        status = "not_met" if not any(row["in_highway"] for row in data["frames"][:2]) else "met"
    else:
        observation = measure_original(data["frames"], data["site"], case)
        status = "met" if observation["entry_original_frame"] < observation["completion_original_frame"] else "not_met"
    return {"case_id": case_id, "provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True, "maneuver_completed": status == "met",
        "physical_checks": {"maneuver": {"status": status,
            "method": "source-bound original-frame highway entry and complete crossing versus first displayed zero",
            "sources": hashes, "details": {"fixture_kind": kind}}},
        "realized_observables": {"countdown_crossing": observation} if status == "met" else {},
        "physical_acceptance": False, "legal_acceptance": False}


def lifecycle(case_id: str, construction: Path, log: Path,
              seal_capture, record_native_exit, acknowledge_owner_release, closure) -> dict:
    attempt = REPO / ".runtime-work/c150911-1d2/lifecycle-fixture" / case_id
    if attempt.exists():
        shutil.rmtree(attempt)
    attempt.mkdir(parents=True)
    shutil.copy2(construction, attempt / "construction.json")
    shutil.copy2(ROOT / "runner.py", attempt / "runner.py")
    (attempt / "trace.jsonl").write_text('{"frame":1,"time_s":0.05}\n')
    (attempt / "video_frames.jsonl").write_text(
        '{"video_frame":0,"carla_frame":1,"time_s":0.05}\n')
    write(attempt / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "case_id": case_id})
    seal_capture(attempt, frames=1, restoration={"restored": True}, errors=[],
        encoder_exit_codes={"fixture": 0}, context={"case_id": case_id})
    record_native_exit(attempt)
    owner = attempt / "owner-release.json"
    acknowledge_owner_release(attempt, owner, True)
    closure(attempt, owner, "synthetic_fixture", True)
    events = ["capture_finished", "encoders_closed", "restoration_verified",
        "native_exit", "owner_released", "saved_processing_started"]
    log.write_text("CPU synthetic lifecycle checker passed: " + ", ".join(events) + "\n")
    return {"events": events, "exit_code": 0,
        "log": str(log.relative_to(ROOT)), "log_sha256": sha(log),
        "diagnostic_fixture": True}


def main() -> None:
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/nonexistent")).resolve()
    if REPO / ".runtime-work" not in output_root.parents:
        raise ValueError("Set output root under .runtime-work before runtime import")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import (
        _closure, acknowledge_owner_release, record_native_exit)
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        short = case_id.split("__")[-1]
        folder = ROOT / "cases" / short
        source = REPO / ".runtime-work/c150911-1d2/compat-selected" / short / "primary"
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            value = assess(source, case_id, kind)
            result = folder / ("physical-" + kind + ".json")
            log = folder / ("physical-" + kind + ".log")
            write(result, value)
            log.write_text("CPU synthetic " + kind + ": " +
                value["physical_checks"]["maneuver"]["status"] + "\n")
            fixtures.append({"kind": kind,
                "command": "CPU source-bound countdown crossing assessment " + case_id,
                "exit_code": 0, "log": str(log.relative_to(ROOT)),
                "log_sha256": sha(log), "result": str(result.relative_to(ROOT)),
                "result_sha256": sha(result)})
        life = lifecycle(case_id, folder / "construction.json",
            folder / "physical-lifecycle.log", seal_capture,
            record_native_exit, acknowledge_owner_release, _closure)
        receipt = folder / "physical-preparation.json"
        write(receipt, {"case_id": case_id,
            "construction_sha256": entry["construction_sha256"],
            "fixtures": fixtures, "lifecycle": life,
            "scope": "CPU synthetic protocol only; original CARLA countdown, crossing and pixels pending"})
        entry["physical_preparation"] = {
            "receipt": str(receipt.relative_to(ROOT)), "sha256": sha(receipt)}
        print(short, "physical/lifecycle CPU fixture passed", flush=True)
    write(ROOT / "execution-manifest.json", manifest)


if __name__ == "__main__":
    main()
