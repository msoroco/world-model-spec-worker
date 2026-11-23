"""Build private, synthetic positive and negative delivery audit attempts."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from delivery_audit import audit
from geometry_audit import audit as geometry_audit
from native_camera import VIEWS
from saved_measurement import finalize_attempt, sha
from source_decode import audit_four_sources


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pattern_videos(private: Path) -> dict[str, Path]:
    folder = private / "pattern_videos"
    folder.mkdir(parents=True, exist_ok=True)
    videos = {}
    for name, width, height in VIEWS:
        path = folder / (name + ".mkv")
        if not path.exists():
            subprocess.run([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "lavfi", "-i", f"color=c=blue:s={width}x{height}:r=20",
                "-vf", "drawbox=x=0:y=0:w=iw/2:h=ih/2:color=red:t=fill",
                "-frames:v", "900", "-an", "-c:v", "ffv1", "-threads", "1",
                "-fflags", "+bitexact", "-flags:v", "+bitexact", str(path)], check=True)
        videos[name] = path
    return videos


def build(case_index: int, output_root: Path) -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    case_id = plan["cases"][case_index]["case_id"]
    suffix = case_id.rsplit("__", 1)[-1]
    source = HERE / "diagnostic_sources" / suffix
    positive = output_root / str(case_index) / "positive"
    positive.mkdir(parents=True, exist_ok=False)
    for name in ("native-run-status.json", "native-exit.json", "owner-release.json",
                 "trace.jsonl", "video_frames.jsonl", "media-receipt.json"):
        shutil.copyfile(source / name, positive / name)
    shutil.copytree(source / "site", positive / "site")
    videos = pattern_videos(output_root)
    receipt = json.loads((positive / "media-receipt.json").read_text())
    for name, video in videos.items():
        os.link(video, positive / (name + ".mkv"))
        receipt["video_sha256"][name] = sha(video)
    (positive / "media-receipt.json").write_text(json.dumps(receipt) + "\n")
    finalize_attempt(positive, positive / "analysis-report.json")
    (positive / "geometry-audit.json").write_text(
        json.dumps(geometry_audit(positive), indent=2) + "\n")
    audit_four_sources(positive)
    checked = audit(positive)
    (positive / "delivery-audit.json").write_text(json.dumps(checked, indent=2) + "\n")
    if checked["case_id"] != case_id or checked["feature_visibility_verified"] is not False:
        raise ValueError("synthetic delivery proof identity or limitation differs")
    negative = output_root / str(case_index) / "negative"
    shutil.copytree(positive, negative)
    result_path = negative / "result.json"
    result = json.loads(result_path.read_text())
    result["maneuver_completed"] = not result["maneuver_completed"]
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    command = [sys.executable, str(HERE / "delivery_proof.py"), "--case", case_id,
               "--attempt", str(positive)]
    negative_command = [sys.executable, str(HERE / "delivery_proof.py"), "--case", case_id,
                        "--attempt", str(negative)]
    passed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    rejected = subprocess.run(negative_command, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    positive_log = HERE / ("proof-" + suffix + "-delivery-positive.log")
    negative_log = HERE / ("proof-" + suffix + "-delivery-negative.log")
    positive_log.write_text(passed.stdout)
    negative_log.write_text(rejected.stdout)
    error = "saved analysis differs from original source remeasurement"
    if passed.returncode != 0 or rejected.returncode == 0 or error not in rejected.stdout:
        raise ValueError("positive/negative delivery audit proof failed")
    proof = {"case_id": case_id, "sets": ["full-test"],
             "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                        "actual_pixels", "physical_completion"],
             "command": " ".join(command), "test_exit_code": passed.returncode,
             "test_log": positive_log.name, "test_log_sha256": digest(positive_log),
             "negative_command": " ".join(negative_command),
             "negative_exit_code": rejected.returncode,
             "negative_expected_error": error,
             "negative_log": negative_log.name, "negative_log_sha256": digest(negative_log),
             "script": "delivery_proof.py", "script_sha256": digest(HERE / "delivery_proof.py"),
             "scope": "synthetic CPU audit path; no crossing feature visibility or physical acceptance",
             "feature_visibility_verified": False, "physical_acceptance_claimed": False}
    (HERE / ("delivery-" + suffix + "-receipt.json")).write_text(
        json.dumps(proof, indent=2) + "\n")
    return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-index", type=int, choices=range(6), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"case_id": build(args.case_index, args.output_root)["case_id"],
                      "positive_and_negative": "passed"}))
