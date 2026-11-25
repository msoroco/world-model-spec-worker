"""Exercise three source-bound diagnostic physical outcomes for one exact case."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


VARIANTS = ("nearest_view_hold", "nearest_view_continue", "nearest_view_clear",
            "active_signal_exception")
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=VARIANTS, required=True)
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    source = args.scratch / ("compat-hold-v5" if args.case == "nearest_view_hold"
                             else "compat-" + args.case + "-v5")
    stage = args.scratch / ("physical-" + args.case + "-" + args.kind)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for name in ("config.json", "video_frames.jsonl", "trace.jsonl",
                 "control_context.json", "acquisition-provenance.json"):
        shutil.copyfile(source / name, stage / name)
    if args.kind == "complete_motion":
        shutil.copyfile(source / "interaction_history.jsonl",
                        stage / "interaction_history.jsonl")
    elif args.kind == "incomplete_motion":
        rows = [json.loads(line) for line in
                (source / "interaction_history.jsonl").read_text().splitlines()]
        first = rows[0]["ego"]["body_vertices_m"]
        for row in rows:
            row["ego"]["body_vertices_m"] = first
        (stage / "interaction_history.jsonl").write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
    sys.path.insert(0, str(Path("runtime/scenario_pipeline").resolve()))
    from worker_exchange.native_output import physical_result
    base = json.loads((source / "result.json").read_text())
    result = physical_result(stage, base)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[args.kind]
    actual = result["physical_checks"]["maneuver"]["status"]
    assert actual == expected, (args.case, args.kind, actual, expected)
    assert result["provenance_kind"] == "synthetic_fixture"
    assert result["diagnostic_fixture"] is True
    assert result["maneuver_completed"] == (expected == "met")
    assert result["physical_checks"]["maneuver"]["sources"]
    args.result.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(json.dumps({"case": args.case, "kind": args.kind, "status": actual,
                      "diagnostic_fixture": True,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
