"""Three synthetic physical-outcome tests for each exact construction."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
private = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not private or not Path(private).resolve().is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result


def run(case: str, kind: str) -> dict:
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("unknown physical fixture kind")
    suffix = case.rsplit("__", 1)[-1]
    construction = ROOT / ("construction.json" if suffix == "slow_center_wide"
                           else "cases/" + suffix + "/construction.json")
    bundle = json.loads(construction.read_text(encoding="utf-8"))
    if bundle["case_id"] != case:
        raise ValueError("physical fixture case differs")
    config = json.loads(next(item["content"] for item in bundle["files"]
                             if item["path"] == "config.json"))
    Path(private).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c323986-physical-", dir=private) as temporary:
        root = Path(temporary)
        (root / "config.json").write_text(json.dumps(config) + "\n")
        rows = []
        mapping = []
        for index in range(900):
            x = index * 0.2 if kind == "complete_motion" else 0
            rows.append({"frame": index, "time_s": index / 20,
                         "position_m": [x, 0, 0], "heading_deg": 0,
                         "speed_mps": 4 if kind == "complete_motion" else 0})
            mapping.append({"carla_frame": index, "video_frame": index,
                            "time_s": index / 20})
        if kind != "missing_evidence":
            (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in mapping))
        result = physical_result(root, {"case_id": case, "target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    if result["physical_checks"]["maneuver"]["status"] != expected:
        raise AssertionError("physical outcome differs from original evidence: " +
                             json.dumps(result["physical_checks"]["maneuver"]))
    if result["maneuver_completed"] != (expected == "met"):
        raise AssertionError("completion boolean differs from evidence")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.case, args.kind, result["physical_checks"]["maneuver"]["status"])


if __name__ == "__main__":
    main()
