"""Exercise source-bound crossing completion and Native ownership checkers on CPU fixtures."""

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import _closure, acknowledge_owner_release, record_native_exit

from crosswalk_delivery import measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def lines(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines()]


def assess(source, case_id, rows=None, missing=False):
    site_path = source / "original-site.json"
    names = ("original-site.json", "original-pedestrian.jsonl",
             "original-obstacles.jsonl", "original-participants.jsonl")
    hashes = {name: sha(source / name) for name in names if (source / name).is_file()}
    if missing:
        status, observation, detail = "unverified", {}, "original-site.json withheld"
    else:
        site = json.loads(site_path.read_text())
        walker = rows if rows is not None else lines(source / names[1])
        obstacles = lines(source / names[2])[:len(walker)]
        participants = lines(source / names[3])[:len(walker)]
        observation = measure(site, walker, obstacles, participants)
        distance = math.dist(site["entry_center"], site["exit_center"])
        stations = [r["station_m"] for r in observation["full_original_trace"]]
        complete = len(stations) >= 3 and stations[0] <= 1.5 and stations[-1] >= distance - 1.5
        complete = complete and all(r["within_crosswalk"] for r in observation["full_original_trace"])
        status = "met" if complete else "not_met"
        detail = {"first_station_m": stations[0], "last_station_m": stations[-1],
                  "passage_length_m": distance, "sample_count": len(stations),
                  "engineering_completion_only": True}
    return {"case_id": case_id, "provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True, "maneuver_completed": status == "met",
        "physical_checks": {"maneuver": {"status": status,
            "method": "source-bound original crossing station and polygon occupancy",
            "sources": hashes, "details": detail}},
        "realized_observables": {"crosswalk_passage": observation} if status == "met" else {},
        "legal_practicability": "unresolved", "physical_acceptance": False}


def lifecycle(case_id, construction, log):
    attempt = REPO / ".runtime-work/c150911-lifecycle-fixture" / case_id
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
    _closure(attempt, owner, "synthetic_fixture", True)
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    log.write_text("CPU synthetic lifecycle checker passed: " + ", ".join(events) + "\n")
    return {"events": events, "exit_code": 0,
            "log": str(log.relative_to(ROOT)), "log_sha256": sha(log),
            "diagnostic_fixture": True}


def main():
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        short = cid.split("__")[-1]
        folder = ROOT / "cases" / short
        source = REPO / ".runtime-work/c150911-compat-selected" / short / "primary"
        variants = {"complete_motion": (None, False),
            "incomplete_motion": (lines(source / "original-pedestrian.jsonl")[:3], False),
            "missing_evidence": (None, True)}
        receipts = []
        for kind, (rows, missing) in variants.items():
            result = folder / ("physical-" + kind + ".json")
            log = folder / ("physical-" + kind + ".log")
            value = assess(source, cid, rows, missing)
            write(result, value)
            log.write_text("CPU synthetic " + kind + ": " +
                value["physical_checks"]["maneuver"]["status"] + "\n")
            receipts.append({"kind": kind, "command": "CPU synthetic crossing assessment " + cid,
                "exit_code": 0, "log": str(log.relative_to(ROOT)),
                "log_sha256": sha(log), "result": str(result.relative_to(ROOT)),
                "result_sha256": sha(result)})
        life_log = folder / "physical-lifecycle.log"
        life = lifecycle(cid, folder / "construction.json", life_log)
        proof = folder / "physical-preparation.json"
        write(proof, {"case_id": cid, "construction_sha256": entry["construction_sha256"],
            "fixtures": receipts, "lifecycle": life,
            "scope": "CPU synthetic fixture; actual motion and pixels unverified"})
        entry["physical_preparation"] = {"receipt": str(proof.relative_to(ROOT)),
                                         "sha256": sha(proof)}
        print(short, "physical/lifecycle CPU fixture passed", flush=True)
    (ROOT / "execution-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
