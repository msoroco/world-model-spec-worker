"""CPU diagnostic physical outcomes for the selected source audit contract.

The input is a synthetic compatibility attempt. This script never certifies
original motion or an actual legal result.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from curb_entry import CASES

ASSIGNMENT = "testing__C228096__NRS-484B-283-1b__pedestrian"
VARIANTS = {item.name for item in CASES}


def run(case: str, kind: str, attempt: Path, output: Path) -> dict:
    if case not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS}:
        raise ValueError("exact case required")
    if kind not in {"complete_motion", "incomplete_motion", "missing_evidence"}:
        raise ValueError("unknown physical fixture kind")
    if output.exists():
        raise ValueError("fresh diagnostic result required")
    root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix="c228096-physical-") as tmp:
        stage = Path(tmp)
        for name in ("config.json", "trace.jsonl", "video_frames.jsonl",
                     "acquisition-provenance.json"):
            shutil.copy2(attempt / name, stage / name)
        base = json.loads((attempt / "result.json").read_text(encoding="utf-8"))
        if base["case_id"] != case or base.get("diagnostic_fixture") is not True:
            raise ValueError("physical proof requires exact synthetic attempt")
        if kind in {"complete_motion", "incomplete_motion"}:
            path = stage / "trace.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            fixed = dict(rows[0]["position"])
            fixed_m = list(rows[0]["position_m"])
            for i, row in enumerate(rows):
                progress = i * 0.2 if kind == "complete_motion" else 0.0
                row["position"] = dict(fixed, x=fixed["x"] + progress)
                row["position_m"] = [fixed_m[0] + progress, fixed_m[1], fixed_m[2]]
            path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n"
                                    for row in rows), encoding="utf-8")
        elif kind == "missing_evidence":
            (stage / "trace.jsonl").unlink()
        from scenario_pipeline.worker_exchange.native_output import physical_result
        result = physical_result(stage, base)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    actual = result["physical_checks"]["maneuver"]["status"]
    if actual != expected or result["maneuver_completed"] != (expected == "met"):
        raise ValueError("physical fixture classified incorrectly: " + actual)
    if result.get("provenance_kind") != "synthetic_fixture" or result.get("diagnostic_fixture") is not True:
        raise ValueError("diagnostic provenance lost")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"case_id": case, "kind": kind, "status": actual,
            "diagnostic_fixture": True, "result": str(output)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--attempt", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.case, a.kind, a.attempt, a.output), sort_keys=True))


if __name__ == "__main__":
    main()
