"""Exercise pinned physical completion on three synthetic source outcomes.

Run with SCENARIO_PIPELINE_OUTPUT_ROOT exported under .runtime-work first.
This does not assert actual Native motion or legal compliance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUTPUT = REPO / ".runtime-work" / "c150530-physical-outcomes"
CASES = ("near_stand", "far_stand", "near_stand_straight")
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(case: str, kind: str) -> Path:
    folder = ROOT / "cases" / case
    stage = OUTPUT / case / kind
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    construction = json.loads((folder / "construction.json").read_text())
    config = next(item["content"] for item in construction["files"] if item["path"] == "config.json")
    (stage / "config.json").write_text(config)
    for name in ("original-trace.jsonl", "trace.jsonl", "video_frames.jsonl",
                 "acquisition-provenance.json"):
        shutil.copyfile(folder / "diagnostic-sources" / name, stage / name)
    if kind == "incomplete_motion":
        rows = [json.loads(line) for line in (stage / "original-trace.jsonl").read_text().splitlines()]
        destination = 12 if case == "near_stand_straight" else 11
        for row in rows:
            if row["road_id"] == destination:
                row["road_id"] = 11 if destination == 12 else 12
        (stage / "original-trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    if kind == "missing_evidence":
        (stage / "original-trace.jsonl").unlink()
    return stage


def main() -> None:
    destination = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not destination or not Path(destination).resolve().is_relative_to(REPO / ".runtime-work"):
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
    from worker_exchange.native_output import physical_result

    for case in CASES:
        folder = ROOT / "cases" / case
        construction_hash = sha(folder / "construction.json")
        receipts = []
        for kind in KINDS:
            stage = prepare(case, kind)
            result = physical_result(stage, {"target_checks": []})
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            actual = result["physical_checks"]["maneuver"]["status"]
            if actual != expected or result["maneuver_completed"] != (kind == "complete_motion"):
                raise ValueError(f"{case}/{kind}: expected {expected}, got {actual}")
            target = folder / ("physical-" + kind + "-result.json")
            target.write_text(json.dumps(result, indent=2) + "\n")
            log = folder / ("physical-" + kind + ".log")
            log.write_text(f"{case} {kind}: {actual}; source-bound synthetic assessment passed\n")
            receipts.append({"kind": kind, "command": "export SCENARIO_PIPELINE_OUTPUT_ROOT=\"$PWD/.runtime-work/c150530-physical-outcomes-output\"; PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" + ROOT.name + "/prove_physical_outcomes.py",
                             "exit_code": 0,
                             "log": log.relative_to(ROOT).as_posix(), "log_sha256": sha(log),
                             "result": target.relative_to(ROOT).as_posix(),
                             "result_sha256": sha(target)})
        report = {"format": "c150530-physical-preparation-partial-v1",
                  "case_id": ROOT.name + "__" + case,
                  "construction_sha256": construction_hash,
                  "fixtures": receipts,
                  "lifecycle": {"status": "pending tested native-exit and owner-release ordering"},
                  "delivery_ready": False}
        (folder / "physical-preparation.partial.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
