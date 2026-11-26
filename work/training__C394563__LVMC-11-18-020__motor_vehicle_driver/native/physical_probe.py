"""Exercise physical completion outcomes on source-labeled CPU fixtures.

These fixtures test the selected evidence rule; they do not claim a Native run.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "").endswith(".runtime-work/c394563-physical-root"):
        raise ValueError("Set the pinned CPU output root under .runtime-work")
    from worker_exchange.native_output import physical_result

    source = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    original = json.loads((source / "result.json").read_text())
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        folder = output / kind
        folder.mkdir()
        for name in ("config.json", "video_frames.jsonl", "trace.jsonl",
                     "body_history.jsonl", "road_geometry.json"):
            shutil.copyfile(source / name, folder / name)
        if kind == "incomplete_motion":
            lines = (folder / "body_history.jsonl").read_text().splitlines()
            (folder / "body_history.jsonl").write_text("\n".join(lines[:180]) + "\n")
        elif kind == "missing_evidence":
            (folder / "body_history.jsonl").unlink()
        result = physical_result(folder, dict(original))
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        actual = result["physical_checks"]["maneuver"]["status"]
        if actual != expected or result["maneuver_completed"] != (expected == "met"):
            raise ValueError(f"{kind} expected {expected}, observed {actual}")
        (folder / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        (folder / "test.log").write_text(
            f"{kind}: {actual}; source-bound synthetic CPU fixture; physical acceptance not claimed\n")
        print(f"{kind}: {actual}")


if __name__ == "__main__":
    main()
