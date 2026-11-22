"""Verify a materialized synthetic saved fixture and missing-source rejection.

This never claims Native, pixel, legal, or delivery acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from parking_finalizer import finalize
from parking_pose import REQUESTS


REPO = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def verify(fixture, kind):
    fixture = Path(fixture).resolve()
    if kind not in REQUESTS or not fixture.is_dir():
        raise ValueError("exact materialized fixture required")
    scratch = (REPO / ".runtime-work").resolve()
    if not fixture.is_relative_to(scratch):
        raise ValueError("diagnostic fixture must remain under .runtime-work")
    original = fixture / "parking-history.jsonl"
    digest = sha(original)
    packet = fixture / "reviewed-context.json"
    result = finalize(packet, fixture, kind, original, digest)
    history, mapping, camera, trace = [rows(fixture / name) for name in
        ("parking-history.jsonl", "video_frames.jsonl", "camera-frame-map.jsonl", "trace.jsonl")]
    if not len(history) == len(mapping) == len(camera) == len(trace) == 5:
        raise ValueError("diagnostic stream lengths differ")
    for index, group in enumerate(zip(history, mapping, camera, trace)):
        frame = index + 1
        if (group[0]["frame"] != frame or group[1]["carla_frame"] != frame
                or group[1]["video_frame"] != index or group[2]["frame"] != frame
                or group[3]["frame"] != frame
                or any(abs(row["time_s"] - frame / 20) > 1e-9 for row in group)):
            raise ValueError("diagnostic frame/time join differs")
    videos = {}
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        path = fixture / (name + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-count_frames", "-show_entries",
                                "stream=nb_read_frames,width,height,r_frame_rate", "-of", "json",
                                str(path)], capture_output=True, text=True, check=True)
        stream = json.loads(probe.stdout)["streams"][0]
        dimensions = (1920, 1080) if name == "overview" else (1280, 720)
        if (int(stream["nb_read_frames"]) != 5 or
                (stream["width"], stream["height"]) != dimensions or
                stream["r_frame_rate"] != "20/1"):
            raise ValueError("diagnostic camera contract differs: " + name)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i",
                        str(path), "-f", "null", "-"], capture_output=True, check=True)
        videos[name] = {"sha256": sha(path), "frames_fully_decoded": 5}
    with TemporaryDirectory(dir=scratch, prefix="c150041-negative-") as temporary:
        negative = Path(temporary)
        shutil.copy2(packet, negative / "reviewed-context.json")
        shutil.copytree(fixture / "reviewed_sources", negative / "reviewed_sources")
        (negative / "reviewed_sources" / "activity.txt").unlink()
        try:
            finalize(negative / "reviewed-context.json", negative, kind, original, digest)
        except ValueError as exc:
            if "activity original source missing" not in str(exc):
                raise
            negative_error = str(exc)
        else:
            raise ValueError("missing activity source passed saved finalization")
    try:
        finalize(packet, fixture, kind, original, "0" * 64)
    except ValueError as exc:
        if "original stationary history hash changed" not in str(exc):
            raise
        changed_hash_error = str(exc)
    else:
        raise ValueError("changed original history hash passed saved finalization")
    return {"format": "c150041-synthetic-saved-fixture-proof", "case_id": result["case_id"],
            "diagnostic_only": True, "passed": True, "fixture_path": str(fixture),
            "packet_sha256": result["source_packet_sha256"], "history_sha256": digest,
            "stationary_intervals": result["stationary_intervals"],
            "video_sources": videos, "time_joined_frames": 5,
            "missing_source_rejection": negative_error,
            "changed_hash_rejection": changed_hash_error,
            "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    proof = verify(args.fixture, args.case)
    Path(args.output).write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"case_id": proof["case_id"], "passed": True,
                      "diagnostic_only": True, "time_joined_frames": 5}))
