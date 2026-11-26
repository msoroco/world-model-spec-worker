"""Exact C24758 saved-source join before any physical or legal acceptance."""
import hashlib
import json
import subprocess
from pathlib import Path

from sight_speed_measure import EXPECTED_ID, measure, require

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_saved(attempt, output, expected_case=None):
    attempt = Path(attempt).resolve()
    seal = json.loads((attempt / "saved-source.json").read_text())
    require(seal.get("assignment_id") == EXPECTED_ID, "saved assignment mismatch")
    require(seal.get("case_id") == (expected_case or EXPECTED_ID + "__reference"),
            "saved case mismatch")
    require(seal.get("duration_s") == 30 and seal.get("frame_rate_hz") == 20,
            "saved duration mismatch")
    map_path = attempt / "frame-map.json"
    require(sha(map_path) == seal.get("frame_map_sha256"), "frame map sha256 mismatch")
    rows = json.loads(map_path.read_text())
    require(len(rows) == 600, "frame map length mismatch")
    first_native = rows[0].get("native_frame")
    require(type(first_native) is int and first_native >= 0, "native frame origin missing")
    for i, row in enumerate(rows):
        require(row.get("video_frame") == i and row.get("native_frame") == first_native + i
                and abs(row.get("time_s", -1) - i / 20) < 0.0001,
                "frame map identity mismatch")
    videos = seal.get("cameras", {})
    require(set(videos) == set(CAMERAS), "four-camera inventory mismatch")
    camera_hashes = {}
    for name in CAMERAS:
        spec = videos[name]
        path = attempt / spec["path"]
        require(path.is_file() and sha(path) == spec["sha256"],
                f"camera source hash mismatch: {name}")
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                "-select_streams", "v:0", "-show_entries",
                                "stream=nb_read_frames,r_frame_rate", "-of", "json",
                                str(path)], capture_output=True, text=True, check=True)
        streams = json.loads(probe.stdout).get("streams", [])
        require(len(streams) == 1 and streams[0].get("nb_read_frames") == "600"
                and streams[0].get("r_frame_rate") == "20/1",
                f"camera frame contract mismatch: {name}")
        camera_hashes[name] = spec["sha256"]
    observation = attempt / seal["observation_path"]
    measured = measure(observation, seal["observation_sha256"])
    result = {"format": "worker-saved-sight-speed-join-v1",
              "assignment_id": EXPECTED_ID, "case_id": seal["case_id"],
              "frame_map_sha256": seal["frame_map_sha256"],
              "camera_sha256": camera_hashes,
              "measurement": measured,
              "physical_acceptance": None, "legal_verdict": None}
    Path(output).write_text(json.dumps(result, indent=2) + "\n")
    return result
