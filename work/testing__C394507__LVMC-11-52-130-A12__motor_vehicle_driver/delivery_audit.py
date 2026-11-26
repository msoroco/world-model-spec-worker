"""Independent exact-case crossing source, timeline and four-video audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import crosswalk_site as crossing
from crosswalk_measure import measure, require_file
from native_capture import VIEWS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decode(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
                            "-of", "json", str(path)], capture_output=True,
                           text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "ffv1":
        raise ValueError("original camera codec differs")
    process = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                              "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True)
    if process.returncode:
        raise ValueError("original camera full decode failed: " + process.stderr[-300:])
    return {"sha256": sha(path), "decoded_frames": int(streams[0]["nb_read_frames"]),
            "dimensions": [streams[0]["width"], streams[0]["height"]],
            "fps": streams[0]["avg_frame_rate"]}


def audit(attempt, case_id, plan):
    attempt = Path(attempt)
    planned = json.loads(Path(plan).read_text())
    if (case_id not in {case["case_id"] for case in planned["cases"]} or
            not case_id.startswith(crossing.ASSIGNMENT_ID + "__")):
        raise ValueError("exact crossing delivery case differs")
    history = json.loads(require_file(attempt, "original-crosswalk-history.json").read_text())
    diagnostic = (attempt / "fixture-provenance.json").is_file()
    measured = measure(attempt, case_id, diagnostic=diagnostic)
    mapping = rows(require_file(attempt, "video_frames.jsonl"))
    trace = rows(require_file(attempt, "trace.jsonl"))
    evidence = rows(require_file(attempt, "capture/evidence.jsonl"))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(evidence):
        raise ValueError("original actor/video frame counts differ")
    if (len(history["samples"]) != len(mapping) or any(
            packet["frame"] != mapped["carla_frame"] or
            packet["time_s"] != mapped["time_s"] or
            movement["frame"] != mapped["carla_frame"] or
            actor["original_frame"] != mapped["carla_frame"]
            for packet, mapped, movement, actor in
            zip(history["samples"], mapping, trace, evidence))):
        raise ValueError("original crossing/video/source identity join differs")
    videos = {view: decode(require_file(attempt, view + ".mkv")) for view in VIEWS}
    if any(info["decoded_frames"] != len(mapping) for info in videos.values()):
        raise ValueError("original four-camera decoded frame count differs")
    if not diagnostic:
        site = json.loads(require_file(attempt, "original-site.json").read_text())
        if len(mapping) != 900 or any(
                sha(require_file(attempt, record["path"])) != record["sha256"]
                for record in site["source_records"].values()):
            raise ValueError("reviewed Native source inventory incomplete")
    return {"format": "c394507-independent-crosswalk-delivery-audit-v1",
            "case_id": case_id, "capture_frames": len(mapping),
            "source_measurement": measured,
            "source_video_join": True, "four_view_full_decode": videos,
            "diagnostic_fixture": diagnostic,
            "actual_pixels_verified": False,
            "physical_acceptance_claimed": False,
            "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite independent audit")
    result = audit(args.attempt, args.case_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
