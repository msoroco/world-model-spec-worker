"""Exercise physical checker outcomes on exact synthetic attempts only."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path


def run(case: str, kind: str, attempt: Path, output: Path) -> dict:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    if case not in {item["case_id"] for item in plan["cases"]}:
        raise ValueError("exact case required")
    if kind not in {"complete_motion", "incomplete_motion", "missing_evidence"}:
        raise ValueError("unknown physical diagnostic kind")
    if output.exists():
        raise ValueError("fresh physical diagnostic output required")
    root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix="c230223-2703-physical-") as temporary:
        stage = Path(temporary)
        for name in ("config.json", "trace.jsonl", "video_frames.jsonl",
                     "acquisition-provenance.json"):
            shutil.copy2(attempt / name, stage / name)
        base = json.loads((attempt / "result.json").read_text())
        if base.get("case_id") != case or base.get("diagnostic_fixture") is not True:
            raise ValueError("exact synthetic attempt required")
        base["realized_observables"] = {"observed_motion_frames": {
            "unit": "count", "method": "20 Hz diagnostic trace readback",
            "time_window": "45-second synthetic episode", "statistic": "count",
            "reference": "trace.jsonl", "value": 900}}
        if kind == "incomplete_motion":
            path = stage / "trace.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            origin = rows[0]["position"]
            xyz = rows[0]["position_m"]
            for row in rows:
                row["position"] = origin
                row["position_m"] = xyz
            path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
        elif kind == "missing_evidence":
            (stage / "trace.jsonl").unlink()
        from scenario_pipeline.worker_exchange.native_output import physical_result
        receipt = physical_result(stage, base)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    if (receipt["physical_checks"]["maneuver"]["status"] != expected or
            receipt["maneuver_completed"] != (expected == "met") or
            receipt.get("diagnostic_fixture") is not True):
        raise ValueError("physical diagnostic outcome differs: " +
                         receipt["physical_checks"]["maneuver"]["status"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    return {"case_id": case, "kind": kind, "expected": expected,
            "diagnostic_fixture": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.attempt, args.output)))


if __name__ == "__main__":
    main()
