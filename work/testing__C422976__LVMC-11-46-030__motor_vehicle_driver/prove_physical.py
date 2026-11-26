"""Classify synthetic physical-completion outcomes without claiming Native success."""

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent


def run(case, kind, attempt, output):
    selected = json.loads((HERE / "diagnostic-execution-manifest.json").read_text())["cases"]
    if case not in {item["case_id"] for item in selected}:
        raise ValueError("exact selected case required")
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("unknown physical fixture kind")
    if output.exists():
        raise ValueError("fresh diagnostic physical result required")
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c422976-physical-") as directory:
        stage = Path(directory)
        for name in ("config.json", "trace.jsonl", "video_frames.jsonl",
                     "acquisition-provenance.json"):
            shutil.copy2(attempt / name, stage / name)
        base = json.loads((attempt / "result.json").read_text())
        if base["case_id"] != case or base.get("diagnostic_fixture") is not True:
            raise ValueError("exact synthetic compatibility attempt required")
        if kind == "missing_evidence":
            (stage / "trace.jsonl").unlink()
        else:
            trace_path = stage / "trace.jsonl"
            rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
            first = dict(rows[0]["position"])
            first_m = list(rows[0]["position_m"])
            for index, row in enumerate(rows):
                movement = index * .2 if kind == "complete_motion" else 0.0
                row["position"] = dict(first, x=first["x"] + movement)
                row["position_m"] = [first_m[0] + movement, first_m[1], first_m[2]]
            trace_path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n"
                                          for row in rows), encoding="utf-8")
        from scenario_pipeline.worker_exchange.native_output import physical_result
        result = physical_result(stage, base)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    status = result["physical_checks"]["maneuver"]["status"]
    if status != expected or result["maneuver_completed"] != (expected == "met"):
        raise ValueError("physical fixture classified incorrectly: " + status)
    if result.get("provenance_kind") != "synthetic_fixture" or result.get("diagnostic_fixture") is not True:
        raise ValueError("synthetic provenance lost")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"case_id": case, "kind": kind, "status": status,
            "diagnostic_fixture": True, "result": str(output)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.attempt, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
