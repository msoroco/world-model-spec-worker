"""Exercise all four saved-only result builders on source-bound CPU fixtures."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from analysis import build_report, saved_result
from bus_route import ROUTES
from test_comparison_audit import make_attempt, sha


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    runtime_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not runtime_root.is_relative_to((REPO / ".runtime-work").resolve()):
        raise ValueError("runtime output root must stay under .runtime-work")
    proof = REPO / ".runtime-work" / "c147332-saved-v7"
    if proof.exists():
        raise ValueError("retain prior saved proof root; select a new version")
    proof.mkdir(parents=True)
    for kind in ROUTES:
        attempt = proof / kind
        make_attempt(attempt, kind)
        materialized = REPO / ".runtime-work" / "c147332-offline-v9" / kind / "primary"
        for name in ("config.json", "construction.json"):
            shutil.copy2(materialized / name, attempt / name)
        positions = [(0.0, -5.4), (3.0, -5.4)] if kind == "adjacent_travel" else (
            [(0.0, -5.4), (3.0, -3.9)] if kind == "lateral_entry" else (
            [(0.0, -1.8), (0.0, -1.8)] if kind == "red_lane_stand" else
            [(0.0, -1.8), (3.0, -1.8)]))
        with (attempt / "trace.jsonl").open("x") as stream:
            for frame, (x, y) in enumerate(positions, 1):
                stream.write(json.dumps({"frame": frame, "time_s": frame / 20,
                                         "position_m": [x, y, 0]}) + "\n")
        with (attempt / "video_frames.jsonl").open("x") as stream:
            for frame in (1, 2):
                stream.write(json.dumps({"video_frame": frame - 1, "carla_frame": frame,
                                         "native_frame": frame, "time_s": frame / 20}) + "\n")
        acquisition = json.loads((attempt / "acquisition.json").read_text())
        for name in ("trace.jsonl", "video_frames.jsonl"):
            acquisition[name] = sha(attempt / name)
        (attempt / "acquisition.json").write_text(json.dumps(acquisition))
        cli_attempt = proof / (kind + "-cli")
        shutil.copytree(attempt, cli_attempt)
        report = build_report(attempt)
        result = saved_result(attempt, report)
        if result["case_id"] != ROOT.name + "__" + kind or not result["target_checks"]:
            raise ValueError("wrong exact saved result")
        print(json.dumps({"case_id": result["case_id"],
                          "physical_status": result["physical_checks"]["maneuver"]["status"],
                          "diagnostic_fixture_only": True,
                          "native_result_validated": True}))
        subprocess.run([sys.executable, str(ROOT / "analysis.py"), "--attempt", str(cli_attempt),
                        "--output", str(cli_attempt / "analysis-report.json")],
                       check=True, capture_output=True, text=True, timeout=60)
        cli_result = json.loads((cli_attempt / "result.json").read_text())
        if cli_result["case_id"] != result["case_id"]:
            raise ValueError("selected saved-only CLI returned a different case")
        negative = proof / (kind + "-negative")
        shutil.copytree(attempt, negative)
        (negative / "lane-signal-history.jsonl").unlink()
        try:
            build_report(negative)
        except ValueError as error:
            if str(error) != "Missing required source: lane-signal-history.jsonl":
                raise
        else:
            raise AssertionError("missing original lane-signal history accepted")


if __name__ == "__main__":
    main()
