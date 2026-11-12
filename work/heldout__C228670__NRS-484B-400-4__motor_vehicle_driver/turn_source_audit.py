"""Independent saved-source audit for one-way to two-way left-turn diagnostics."""
import hashlib
import json
from pathlib import Path
import subprocess

from turn_geometry import measure

SOURCES = ("road_geometry.json", "body_footprints.json", "body_footprints.jsonl",
           "video_frames.jsonl", "trace.jsonl")
CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def audit(saved_analysis, original_attempt, decode=True):
    saved_analysis, original_attempt = Path(saved_analysis), Path(original_attempt)
    report = json.loads((saved_analysis / "analysis-report.json").read_text())
    result = json.loads((saved_analysis / "result.json").read_text())
    config = json.loads((original_attempt / "config.json").read_text())
    case = config["selected_case_id"]
    if report["case_id"] != case or result["case_id"] != case:
        raise ValueError("Case identity differs from saved original")
    binding = report["measurements"]["turn_geometry"]
    for name in SOURCES:
        original = original_attempt / name
        saved = saved_analysis / name
        if not original.is_file() or not saved.is_file() or sha(original) != sha(saved):
            raise ValueError("Saved original source changed: " + name)
        if binding["sources"].get(name) != sha(original):
            raise ValueError("Analysis source hash changed: " + name)
    frames = lines(original_attempt / "video_frames.jsonl")
    bodies = lines(original_attempt / "body_footprints.jsonl")
    trace = lines(original_attempt / "trace.jsonl")
    if not frames or len({len(frames), len(bodies), len(trace)}) != 1:
        raise ValueError("Original frame count differs")
    for i, (frame, body, state) in enumerate(zip(frames, bodies, trace)):
        if (frame["video_frame"] != i or frame["carla_frame"] != body["frame"]
                or body["frame"] != state["frame"]
                or frame["time_s"] != body["time_s"] or body["time_s"] != state["time_s"]):
            raise ValueError("Original frame join differs")
    measured = measure(saved_analysis / "road_geometry.json",
                       saved_analysis / "body_footprints.json")
    if measured != binding["value"] or measured != result["measured_values"]["turn_geometry"]:
        raise ValueError("Saved measurement differs from original geometry")
    source_videos = {}
    for name in CAMERAS:
        video = original_attempt / name
        saved = saved_analysis / name
        if not video.is_file() or not saved.is_file() or sha(video) != sha(saved):
            raise ValueError("Saved camera bytes changed: " + name)
        if decode:
            process = subprocess.run(["ffmpeg", "-v", "error", "-i", str(saved),
                                      "-map", "0:v:0", "-f", "null", "-"],
                                     capture_output=True, text=True)
            if process.returncode:
                raise ValueError("Full source camera decode failed: " + name + ": " + process.stderr[-300:])
            counted = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                      "-select_streams", "v:0", "-show_entries",
                                      "stream=nb_read_frames", "-of",
                                      "default=noprint_wrappers=1:nokey=1", str(saved)],
                                     capture_output=True, text=True)
            if counted.returncode or counted.stdout.strip() != str(len(frames)):
                raise ValueError("Source camera frame count differs: " + name)
        source_videos[name] = sha(video)
    if result.get("physical_acceptance_claimed") or result.get("legal_acceptance_claimed"):
        raise ValueError("Fixture claimed physical or legal acceptance")
    return {"format": "worker-turn-saved-source-audit", "case_id": case,
            "original_frame_count": len(frames), "source_sha256": {n: sha(original_attempt / n) for n in SOURCES},
            "camera_sha256": source_videos, "saved_measurement": measured,
            "full_camera_decode": bool(decode), "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}
