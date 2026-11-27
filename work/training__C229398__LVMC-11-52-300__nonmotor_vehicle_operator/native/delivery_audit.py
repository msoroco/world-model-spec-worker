"""Independent CPU audit of a synthetic diagnostic delivery excerpt.

The nine-frame pixel fixture checks plumbing. The separate full-length meter
checks the boundary; neither fixture is an original Native acceptance.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from duration_policy import TARGETS, TOTAL_FRAMES
from selected_measurement import measure


HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
AID = HERE.name
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def probe_video(path, expected_frames):
    run = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries",
        "stream=nb_read_frames,width,height,r_frame_rate", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=180)
    require(run.returncode == 0, "Full video decode failed")
    streams = json.loads(run.stdout).get("streams", [])
    require(len(streams) == 1, "One video stream required")
    row = streams[0]
    require(row.get("nb_read_frames") == str(expected_frames) and
            row.get("r_frame_rate") == "20/1", "Diagnostic video frame count differs")
    pixels = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=180)
    require(pixels.returncode == 0 and len(pixels.stdout) ==
            int(row["width"]) * int(row["height"]) * 3, "Actual decoded pixels missing")
    return {"frames": expected_frames, "width": int(row["width"]),
            "height": int(row["height"]), "sha256": digest(path),
            "first_pixel_sha256": hashlib.sha256(pixels.stdout).hexdigest()}


def audit(case, attempt, negative=False):
    suffix = case.rsplit("__", 1)[-1]
    require(case == AID + "__" + suffix and suffix in TARGETS,
            "Wrong exact duration case")
    attempt = Path(attempt).resolve()
    require((REPO / ".runtime-work").resolve() in attempt.parents,
            "Diagnostic attempt must be ignored scratch")
    required = {"config.json", "native-actor-frames.jsonl", "video_frames.jsonl",
                "review-source.json", "street-geometry.json"}
    require(all((attempt / name).is_file() for name in required),
            "Diagnostic source inventory incomplete")
    if negative:
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work",
                                         prefix="c229398-delivery-negative-") as temporary:
            root = Path(temporary)
            for name in required - {"native-actor-frames.jsonl"}:
                shutil.copy2(attempt / name, root / name)
            packet = json.loads((root / "review-source.json").read_text())
            for item in packet["sources"].values():
                shutil.copy2(attempt / item["path"], root / item["path"])
            measure(root)
        raise ValueError("Negative source unexpectedly accepted")
    measured = measure(attempt)
    require(measured["case_id"] == case and measured["diagnostic_excerpt"] is True
            and measured["frame_count"] == 9 and measured["source_kind"] == "synthetic_cpu",
            "Source joined diagnostic excerpt differs")
    require(measured["review_supported"] is True,
            "Source-bound nonmotor participants or street not supported")
    videos = {view: probe_video(attempt / (view + ".mkv"), 9) for view in VIEWS}
    physical = json.loads((HERE / "physical" / suffix / "complete_motion-result.json").read_text())
    observed = physical.get("realized_observables", {}).get("night_parking_duration_ms")
    require(physical.get("diagnostic_fixture") is True and
            physical.get("physical_checks", {}).get("maneuver", {}).get("status") == "met"
            and observed == TARGETS[suffix] * 1000,
            "Full-length synthetic physical completion differs")
    return {"format": "c229398-delivery-audit-v1", "case_id": case,
            "checks": CHECKS, "diagnostic_excerpt_frames": measured["frame_count"],
            "full_length_synthetic_frames": TOTAL_FRAMES,
            "full_length_duration_ms": observed, "video": videos,
            "original_native_executed": False, "physical_or_legal_acceptance": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--negative-selftest", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.case, arguments.attempt,
                           arguments.negative_selftest), sort_keys=True))


if __name__ == "__main__":
    main()
