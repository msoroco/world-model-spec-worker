"""Exercise the pinned physical assessor on labeled synthetic turn outcomes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not output_root or not Path(output_root).resolve().is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suffix = args.case.rsplit("__", 1)[-1]
    construction = json.loads((ROOT / "constructions" / (suffix + ".json")).read_text())
    if construction["case_id"] != args.case:
        raise ValueError("physical fixture case differs from construction")
    config = json.loads(next(item["content"] for item in construction["files"] if item["path"] == "config.json"))
    if config["physical_completion"]["criterion"] != "turn":
        raise ValueError("selected construction does not author a supported turn criterion")
    private = Path(output_root)
    private.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="physical-", dir=private) as temporary:
        root = Path(temporary)
        (root / "config.json").write_text(json.dumps(config) + "\n")
        frames = [101, 102, 103]
        (root / "video_frames.jsonl").write_text("".join(json.dumps({
            "video_frame": index, "carla_frame": frame, "time_s": index / 20,
        }) + "\n" for index, frame in enumerate(frames)))
        if args.kind != "missing_evidence":
            points = [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [5.0, 5.0, 0.0]]
            headings = [0.0, 45.0, 90.0]
            if args.kind == "incomplete_motion":
                points = [[0.0, 0.0, 0.0]] * 3
                headings = [0.0] * 3
            (root / "trace.jsonl").write_text("".join(json.dumps({
                "frame": frame, "time_s": index / 20,
                "native_frame": {"ego": {"location_xyz_m": points[index]}},
                "heading_deg": headings[index],
            }) + "\n" for index, frame in enumerate(frames)))
        result = physical_result(root, {"case_id": args.case, "target_checks": []})
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        check = result["physical_checks"]["maneuver"]
        if (check["status"] != expected or result["maneuver_completed"] != (expected == "met") or
                result["provenance_kind"] != "synthetic_fixture" or
                result["diagnostic_fixture"] is not True):
            raise AssertionError("pinned physical outcome differs: " + json.dumps(check))
        if args.kind == "complete_motion" and not result["realized_observables"]:
            raise AssertionError("complete synthetic turn lacks measurements")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(args.case, args.kind, expected, "synthetic fixture only")


if __name__ == "__main__":
    main()
