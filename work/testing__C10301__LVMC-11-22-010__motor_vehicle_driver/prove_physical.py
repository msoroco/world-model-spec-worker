"""Exercise source-bound physical outcomes on synthetic CPU trajectories."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence"), required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    if repo / ".runtime-work" not in args.scratch.resolve().parents:
        raise ValueError("Scratch must be under .runtime-work")
    if folder not in args.result.resolve().parents:
        raise ValueError("Result must be under the owned assignment")
    if args.case not in (folder.name + "__steady_travel", folder.name + "__steering_variation"):
        raise ValueError("Foreign exact case")
    kind = args.case.rsplit("__", 1)[1]
    construction = json.loads((folder / ("construction-" + kind + ".json")).read_text())
    if construction["case_id"] != args.case:
        raise ValueError("Construction identity differs")
    cfg = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    stage = args.scratch / (kind + "-" + args.kind)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / "config.json").write_text(json.dumps(cfg) + "\n")
    (stage / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
    mapping = [{"video_frame": i, "carla_frame": i + 100, "time_s": i / 20}
               for i in range(900)]
    (stage / "video_frames.jsonl").write_text("".join(json.dumps(r) + "\n" for r in mapping))
    if args.kind != "missing_evidence":
        rows = []
        for i, frame in enumerate(mapping):
            progress = min(i / 799, 1.0) * (120 if args.kind == "complete_motion" else 0)
            rows.append({"frame": frame["carla_frame"], "time_s": frame["time_s"],
                         "position_m": [140 - progress, 0.0, 0.0]})
        (stage / "trace.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import physical_result
    result = physical_result(stage, {"target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[args.kind]
    actual = result["physical_checks"]["maneuver"]["status"]
    if actual != expected or result["maneuver_completed"] != (expected == "met"):
        raise ValueError("Diagnostic physical outcome differs: " + actual)
    if result["provenance_kind"] != "synthetic_fixture" or result["diagnostic_fixture"] is not True:
        raise ValueError("Diagnostic fixture provenance lost")
    args.result.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "status": actual, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
