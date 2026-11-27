"""Independent source and frame audit for original NRS 484B.270(3) attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from cycle_lane_2703 import ASSIGNMENT, VIEWS, measure_original_frames


def digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("original source missing or linked: " + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sealed(root: Path, ref: dict, expected: str | None = None) -> Path:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise ValueError("sealed original reference required")
    untrusted = root / ref["path"]
    if untrusted.is_symlink():
        raise ValueError("linked original source rejected")
    path = untrusted.resolve()
    if not path.is_relative_to(root) or digest(path) != ref.get("sha256"):
        raise ValueError("sealed original source changed")
    if expected is not None and digest(path) != expected:
        raise ValueError("independent review hash differs")
    return path


def decode(path: Path) -> dict:
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries",
                            "stream=codec_type,width,height,avg_frame_rate,nb_read_frames",
                            "-of", "json", str(path)], capture_output=True, text=True,
                           timeout=180, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("one original camera stream required")
    stream = streams[0]
    if (stream.get("codec_type") != "video" or
            stream.get("avg_frame_rate") != "20/1" or
            int(stream.get("nb_read_frames", -1)) != 900 or
            int(stream.get("width", 0)) < 64 or int(stream.get("height", 0)) < 64):
        raise ValueError("original camera timing or size differs")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                    "-map", "0:v:0", "-f", "null", "-"], capture_output=True,
                   text=True, timeout=180, check=True)
    return {"sha256": digest(path), "frame_count": 900, "full_decode": True}


def audit(attempt: Path, review: dict, case_id: str) -> dict:
    root = attempt.resolve()
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact case required")
    if not (root / "attempt-source.json").is_file():
        raise ValueError("original Native cycle-lane attempt required")
    seal = json.loads((root / "attempt-source.json").read_text())
    if (seal.get("format") != "cycle-lane-2703-native-attempt-v1" or
            seal.get("source_kind") != "original_native" or
            seal.get("diagnostic_fixture") is not False or
            seal.get("case_id") != case_id):
        raise ValueError("original Native cycle-lane attempt required")
    if set(review) != {"site", "participant", "context"}:
        raise ValueError("three independent review hashes required")
    packets = {name: json.loads(sealed(root, seal.get("sources", {}).get(name),
                                       review[name]).read_text())
               for name in review}
    if any(packet.get("source_kind") != "original_reviewed" for packet in packets.values()):
        raise ValueError("reviewed original packets required")
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    case = next((c for c in plan["cases"] if c["case_id"] == case_id), None)
    if case is None:
        raise ValueError("case absent from finite plan")
    if (packets["site"].get("assignment_id") != ASSIGNMENT or
            packets["participant"].get("road_user_kind") != case["road_user_kind"] or
            packets["context"].get("exception_kind") != case["exception_request"]):
        raise ValueError("reviewed site, user or exception differs")
    rows = json.loads(sealed(root, seal.get("history")).read_text())
    measurement = measure_original_frames(
        rows, packets["site"]["facility_polygon"],
        packets["site"]["conflict_polygon"], seal.get("ego_actor_id"),
        seal.get("participant_actor_id"))
    media = {view: decode(sealed(root, seal.get("cameras", {}).get(view)))
             for view in VIEWS}
    return {"format": "cycle-lane-2703-independent-audit-v1", "case_id": case_id,
            "source_kind": "original_native", "review_sha256": review,
            "attempt_source_sha256": digest(root / "attempt-source.json"),
            "history_sha256": digest(root / "history.json"),
            "measurement": measurement, "media": media,
            "checks": {"native_source": True, "all_participants": True,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": False, "physical_completion": False},
            "physical_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(args.review.read_text())
    if Path(packet.get("attempts", {}).get(args.case, "")).resolve() != args.attempt.resolve():
        raise ValueError("reviewed original attempt path differs")
    result = audit(args.attempt, packet.get("reviews", {}).get(args.case, {}), args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "audit": str(args.output)}))


if __name__ == "__main__":
    main()
