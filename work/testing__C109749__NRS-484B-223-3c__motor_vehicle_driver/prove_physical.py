"""Exercise source-bound CPU motion outcomes for one exact lane case.

This synthetic path milestone checks assessment plumbing only. It does not
establish a public highway, actual turn/merge, or a statutory outcome.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence"), required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    repo = base.parents[1]
    if repo / ".runtime-work" not in args.scratch.resolve().parents:
        raise ValueError("Scratch must be under .runtime-work")
    if base not in args.result.resolve().parents:
        raise ValueError("Result must be under owned assignment")
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import physical_result
    suffix = args.case.removeprefix(base.name + "__")
    if args.case != base.name + "__" + suffix:
        raise ValueError("Foreign exact case")
    construction = json.loads((base / "cases" / suffix / "construction.json").read_text())
    if construction["case_id"] != args.case:
        raise ValueError("Construction identity differs")
    config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    stage = args.scratch / (suffix + "-" + args.kind)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / "config.json").write_text(json.dumps(config) + "\n")
    (stage / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
    mapping = [{"video_frame": i, "carla_frame": i + 100, "time_s": i / 20}
               for i in range(900)]
    (stage / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in mapping))
    if args.kind != "missing_evidence":
        rows = [{"frame": row["carla_frame"], "time_s": row["time_s"],
                 "position_m": [120 * i / 899 if args.kind == "complete_motion" else 0, 0.0, 0.0]}
                for i, row in enumerate(mapping)]
        (stage / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = physical_result(stage, {"target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[args.kind]
    actual = result["physical_checks"]["maneuver"]["status"]
    if actual != expected or result["maneuver_completed"] != (expected == "met"):
        raise ValueError("Diagnostic motion assessment differs: " + actual)
    if result["provenance_kind"] != "synthetic_fixture" or result["diagnostic_fixture"] is not True:
        raise ValueError("Diagnostic provenance lost")
    args.result.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "status": actual, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
