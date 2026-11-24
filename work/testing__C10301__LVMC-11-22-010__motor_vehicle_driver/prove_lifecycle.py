"""Test diagnostic capture closure ordering against the pinned runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    if repo / ".runtime-work" not in args.scratch.resolve().parents:
        raise ValueError("Scratch must be under .runtime-work")
    if args.case not in (folder.name + "__steady_travel", folder.name + "__steering_variation"):
        raise ValueError("Foreign exact case")
    kind = args.case.rsplit("__", 1)[1]
    construction = json.loads((folder / ("construction-" + kind + ".json")).read_text())
    if construction["case_id"] != args.case:
        raise ValueError("Construction identity differs")
    stage = args.scratch / (kind + "-lifecycle")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    prior = args.scratch / (kind + "-complete_motion")
    for name in ("config.json", "trace.jsonl", "video_frames.jsonl"):
        shutil.copyfile(prior / name, stage / name)
    (stage / "construction.json").write_text(json.dumps(construction) + "\n")
    (stage / "runner.py").write_text(next(f["content"] for f in construction["files"] if f["path"] == "runner.py"))
    (stage / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure
    seal = seal_capture(stage, frames=900, restoration={"restored": True},
                        errors=[], encoder_exit_codes={"diagnostic": 0})
    if seal["events"] != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("Seal lifecycle differs")
    try:
        acknowledge_owner_release(stage, stage / "owner-release.json", True)
    except ValueError:
        pass
    else:
        raise ValueError("Premature owner release accepted")
    record_native_exit(stage)
    acknowledge_owner_release(stage, stage / "owner-release.json", True)
    _closure(stage, stage / "owner-release.json", "synthetic_fixture", True)
    events = seal["events"] + ["native_exit", "owner_released", "saved_processing_started"]
    print(json.dumps({"case_id": args.case, "events": events,
                      "premature_owner_release_rejected": True,
                      "diagnostic_fixture": True, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
