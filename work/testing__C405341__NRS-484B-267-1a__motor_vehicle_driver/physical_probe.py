"""Synthetic motion outcome and Native ownership closure for each 1a case."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from emergency_construction import CASES
from native_packet import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
HISTORY = "original-emergency-movement-history.jsonl"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def lifecycle(case_id, scratch):
    """Exercise ordering on a labeled short synthetic closure fixture."""
    if not (ROOT / ".runtime-work") in Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve().parents:
        raise ValueError("runtime output root must be under .runtime-work")
    sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        stage = Path(temporary)
        name = case_id.removeprefix(AID + "__")
        construction = json.loads((HERE / ("construction-" + name + ".json")).read_text())
        config = json.loads(next(row["content"] for row in construction["files"]
                                 if row["path"] == "config.json"))
        write(stage / "construction.json", construction)
        write(stage / "config.json", config)
        (stage / "runner.py").write_text((HERE / "runner.py").read_text(encoding="utf-8"), encoding="utf-8")
        write(stage / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
              "diagnostic_fixture": True, "physical_acceptance_claimed": False})
        (stage / "trace.jsonl").write_text("".join(json.dumps({"frame": i + 100,
            "time_s": i / 20, "speed_mps": 1.0}) + "\n" for i in range(9)), encoding="utf-8")
        (stage / "video_frames.jsonl").write_text("".join(json.dumps({
            "video_frame": i, "carla_frame": i + 100, "native_frame": i + 100,
            "time_s": i / 20}) + "\n" for i in range(9)), encoding="utf-8")
        seal = seal_capture(stage, frames=9, restoration={"restored": True,
            "settings_readback": "synthetic CPU closure fixture"}, errors=[],
            encoder_exit_codes={"fixture": 0})
        native_exit = record_native_exit(stage)
        owner = acknowledge_owner_release(stage, stage / "owner-release.json", True)
        with tempfile.TemporaryDirectory(dir=scratch) as saved:
            copy_sources(stage, Path(saved))
        if native_exit["capture_seal_sha256"] != sha(stage / "capture-seal.json") or \
                owner["native_exit_sha256"] != sha(stage / "native-exit.json"):
            raise ValueError("Native lifecycle source hashes differ")
        return seal["events"] + ["native_exit", "owner_released", "saved_processing_started"]


def probe(case_id, kind, output):
    cases = {AID + "__" + case.suffix: case for case in CASES}
    if case_id not in cases or kind not in KINDS:
        raise ValueError("exact case and physical kind required")
    name = cases[case_id].suffix
    folder = HERE / "diagnostics" / name
    site = folder / "emergency-site.json"
    camera = folder / "camera-frame-map.jsonl"
    history = folder / HISTORY
    sources = {p.name: sha(p) for p in (site, camera) if p.is_file()}
    rows = []
    if kind != "missing_evidence":
        rows = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()]
        sources[HISTORY] = sha(history)
        if len(rows) != 900 or [r["frame"] for r in rows] != list(range(900)):
            raise ValueError("complete original-frame diagnostic history required")
    if kind == "incomplete_motion":
        # Distinct synthetic fixture: hold the ego at its first recorded pose.
        origin = rows[0]["ego_xy"]
        rows = [{**row, "ego_xy": origin} for row in rows]
    if kind == "complete_motion":
        displacement = rows[-1]["ego_xy"][0] - rows[0]["ego_xy"][0]
        if abs(displacement) <= 0:
            raise ValueError("ego motion diagnostic absent")
        status = "met"
    elif kind == "incomplete_motion":
        displacement = rows[-1]["ego_xy"][0] - rows[0]["ego_xy"][0]
        if displacement != 0:
            raise ValueError("held-position negative fixture still moves")
        status = "not_met"
    else:
        displacement = None
        status = "unverified"
    result = {"case_id": case_id,
        "physical_checks": {"maneuver": {"status": status,
            "method": "900 source-bound synthetic ego positions and joined camera frames",
            "sources": sources, "original_ego_displacement_m": displacement,
            "legal_verdict_claimed": False}},
        "maneuver_completed": status == "met",
        "realized_observables": {"ego_displacement_m": {"value": displacement,
            "unit": "m", "method": "first to last original ego position", "time_window": "45 s",
            "statistic": "difference", "reference": HISTORY}} if status == "met" else {},
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "physical_acceptance_claimed": False, "legal_judgment": None}
    Path(output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    events = lifecycle(case_id, ROOT / ".runtime-work/c405341-1a/tmp") if kind == "complete_motion" else None
    return {"case_id": case_id, "kind": kind, "status": status, "lifecycle": events,
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe(args.case, args.kind, args.output), sort_keys=True))
