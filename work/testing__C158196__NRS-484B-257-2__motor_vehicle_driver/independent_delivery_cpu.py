"""Exercise independent media and physical checks on synthetic CPU fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from original_camera_recorder import VIEWS
from production_delivery_audit import media_audit, pixel_join, source


ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, scratch, output, negative):
    suffix = case.split("__")[-1]
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    if case not in {item["case_id"] for item in manifest["cases"]}:
        raise ValueError("unknown exact case")
    scratch.mkdir(parents=True, exist_ok=False)
    seal = {"sources": {}}
    joined = {}
    for view in VIEWS:
        video = scratch / (view + ".mkv")
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=blue:s=16x16:r=20", "-frames:v", "3", "-c:v",
                        "ffv1", str(video)], check=True, capture_output=True)
        seal["sources"][video.name] = sha(video)
        png = scratch / (view + ".png")
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(video),
                        "-frames:v", "1", str(png)], check=True,
                       capture_output=True)
        joined[view] = sha(png)
    if negative:
        (scratch / "approach.mkv").unlink()
        source(scratch, "approach.mkv", seal)
        raise ValueError("negative missing original camera source unexpectedly accepted")
    for view in VIEWS:
        video = source(scratch, view + ".mkv", seal)
        media_audit(video, 3, (16, 16))
        pixel_join(video, scratch / (view + ".png"), 1, (16, 16))
    physical_path = ROOT / f"physical-{suffix}-complete_motion-result.json"
    physical = json.loads(physical_path.read_text())
    if physical["physical_checks"]["maneuver"]["status"] != "met" or \
            not physical["realized_observables"]:
        raise ValueError("synthetic measured crossing diagnostic absent")
    value = {"case_id": case, "diagnostic_fixture": True,
             "provenance_kind": "synthetic_fixture", "native_acceptance_claimed": False,
             "physical_fixture_sha256": sha(physical_path),
             "checks": ["native_source", "all_participants", "time_join",
                        "full_video_decode", "actual_pixels", "physical_completion"],
             "original_media_component_checks": list(VIEWS)}
    output.write_text(json.dumps(value, sort_keys=True) + "\n")
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    run(args.case, args.scratch, args.output, args.negative)
