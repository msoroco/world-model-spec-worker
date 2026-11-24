"""Exercise pinned physical outcome checker on labelled synthetic motion."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


SUFFIXES = {"dual_clear", "dual_vehicle_present", "dual_pedestrian_present",
            "dual_pedestrian_late"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion",
                                            "missing_evidence"), required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    scratch = args.scratch.resolve()
    if not scratch.is_relative_to((repo / ".runtime-work").resolve()):
        raise ValueError("physical fixture scratch must be under .runtime-work")
    if not args.result.resolve().is_relative_to(folder):
        raise ValueError("physical fixture result must stay in owned assignment")
    suffix = args.case.removeprefix(folder.name + "__")
    if suffix not in SUFFIXES or args.case != folder.name + "__" + suffix:
        raise ValueError("foreign physical fixture case")
    construction = json.loads((folder / f"construction-{suffix}.json").read_text())
    config = json.loads(next(f["content"] for f in construction["files"]
                             if f["path"] == "config.json"))
    # The production config uses frame_count/fps. The generic pinned physical
    # assessor expresses its planned span with duration_s/rate_hz.
    config["duration_s"] = config["frame_count"] / config["fps"]
    config["rate_hz"] = config["fps"]
    stage = scratch / f"physical-{suffix}-{args.kind}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / "config.json").write_text(json.dumps(config) + "\n")
    (stage / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
    mapping = [{"video_frame": i, "carla_frame": 100 + i,
                "time_s": i / 20} for i in range(900)]
    (stage / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n"
                                                        for row in mapping))
    if args.kind != "missing_evidence":
        rows = []
        for i, frame in enumerate(mapping):
            progress = 120 * i / 899 if args.kind == "complete_motion" else 0
            rows.append({"frame": frame["carla_frame"], "time_s": frame["time_s"],
                         "position_m": [progress, 0, 0]})
        (stage / "trace.jsonl").write_text("".join(json.dumps(row) + "\n"
                                                  for row in rows))
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import physical_result
    result = physical_result(stage, {"target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[args.kind]
    actual = result["physical_checks"]["maneuver"]["status"]
    if actual != expected or result["maneuver_completed"] != (expected == "met"):
        raise ValueError("synthetic physical outcome differs: " + actual)
    if result["provenance_kind"] != "synthetic_fixture" or result["diagnostic_fixture"] is not True:
        raise ValueError("synthetic provenance lost")
    args.result.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "status": actual, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
