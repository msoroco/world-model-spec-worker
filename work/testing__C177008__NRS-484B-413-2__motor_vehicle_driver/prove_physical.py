"""Exercise source-bound turn completion and missing evidence with synthetic rows."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from worker_exchange.native_output import physical_result

ROOT = Path(__file__).resolve().parent


def run(case: str, kind: str) -> dict:
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("unknown physical fixture")
    config = json.loads((ROOT / "config.json").read_text())
    config["selected_case_id"] = case
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c177008-physical-", dir=scratch) as temporary:
        attempt = Path(temporary)
        (attempt / "config.json").write_text(json.dumps(config) + "\n")
        motion = []
        mapping = []
        trace = []
        for index in range(900):
            phase = index / 899
            x = 20 * min(phase * 2, 1)
            y = -20 * max(phase * 2 - 1, 0) if kind == "complete_motion" else 0
            heading = -90 * max(phase * 2 - 1, 0) if kind == "complete_motion" else 0
            body = [[x + dx, y + dy] for dx in (-1, 1) for dy in (-.5, .5)]
            motion.append({"frame": index, "time_s": index / 20,
                           "body_vertices_m": body, "heading_deg": heading,
                           "road_id": 3 if kind == "complete_motion" and index == 899 else 1})
            mapping.append({"carla_frame": index, "time_s": index / 20,
                            "video_frame": index})
            trace.append({"frame": index, "heading_deg": heading})
        for name, rows in (("body_history.jsonl", motion),
                           ("video_frames.jsonl", mapping), ("trace.jsonl", trace)):
            if kind == "missing_evidence" and name == "body_history.jsonl":
                continue
            (attempt / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        result = physical_result(attempt, {"case_id": case, "target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    actual = result["physical_checks"]["maneuver"]["status"]
    if actual != expected or result["maneuver_completed"] != (expected == "met"):
        raise AssertionError(f"{kind}: {actual} != {expected}: {result['physical_checks']['maneuver']}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(args.kind, result["physical_checks"]["maneuver"]["status"])
