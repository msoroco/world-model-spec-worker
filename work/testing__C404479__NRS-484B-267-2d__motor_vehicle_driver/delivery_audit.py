"""Independent exact-case source, frame-join and four-view decode audit."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import check_source, check_joins, measure_case, required, rows
from emergency_construction import CASES
from native_packet import AID, VIEWS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path, frames):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing required video: " + path.name)
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if (len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or
            int(streams[0].get("nb_read_frames", -1)) != frames):
        raise ValueError("four-view full decode profile differs: " + path.name)
    decoded = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                              "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("four-view full decode failed: " + path.name)
    return {"sha256": sha(path), "decoded_frames": frames,
            "dimensions": [streams[0]["width"], streams[0]["height"]],
            "fps": streams[0]["avg_frame_rate"]}


def audit(attempt, case_id, plan):
    attempt = Path(attempt)
    planned = json.loads(Path(plan).read_text())
    if case_id not in {row["case_id"] for row in planned["cases"]}:
        raise ValueError("exact emergency delivery case absent")
    case = next((row for row in CASES if case_id == AID + "__" + row.suffix), None)
    if case is None:
        raise ValueError("exact emergency case differs")
    config = json.loads(required(attempt, "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("attempt selects another emergency case")
    diagnostic, sources = check_source(attempt, case_id)
    history = rows(required(attempt, "original-emergency-movement-history.jsonl"))
    check_joins(attempt, history)
    site = json.loads(required(attempt, "emergency-site.json").read_text())
    measured = measure_case(case, site, history)
    trace = rows(required(attempt, "trace.jsonl"))
    mapping = rows(required(attempt, "video_frames.jsonl"))
    if len(trace) != len(mapping) or any(
            trace[i].get("frame") != mapping[i]["carla_frame"]
            for i in range(len(trace))):
        raise ValueError("trace/video original-frame join differs")
    for row, emergency in zip(trace, history):
        position = row.get("position_m")
        control = row.get("control")
        if (not isinstance(position, list) or len(position) < 2 or
                not isinstance(control, dict) or
                abs(position[0] - emergency["ego_xy"][0]) > 0.05 or
                abs(position[1] - emergency["ego_xy"][1]) > 0.05 or
                abs(row.get("speed_mps", -1) - emergency["ego_speed_mps"]) > 0.05 or
                abs(control.get("brake", -1) - emergency["ego_brake"]) > 0.02):
            raise ValueError("subject motion/control differs between original trace and emergency history")
    videos = {view: decode(attempt / (view + ".mkv"), len(mapping)) for view in VIEWS}
    return {"format": "c404479-2d-independent-emergency-delivery-v1",
            "case_id": case_id, "source_hashes": sources, "measured": measured,
            "capture_frames": len(history), "trace_frames": len(trace),
            "source_video_join": True, "four_view_full_decode": videos,
            "diagnostic_fixture": diagnostic, "actual_pixels_verified": False,
            "physical_acceptance": False, "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing overwrite of independent emergency audit")
    value = audit(args.attempt, args.case_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
