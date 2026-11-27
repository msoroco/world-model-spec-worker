"""Run source-bound signal measurement on a frozen accepted left-turn row."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from accepted_source import verify as verify_accepted, verify_packet_binding
from signal_distance import EvidenceError, measure, verify_source_bindings


DISTRICT_FROM_CASE = {
    "business_continuous": "business", "business_short": "business",
    "residence_continuous": "residential", "residence_short": "residential",
    "other_area_continuous": "other", "other_area_short": "other",
}


def verify_core_time_join(trace: Path, frames_declared: int, samples: list[dict]) -> dict:
    """Join packet sample frames to the admitted original Core scene timeline."""
    try:
        original = json.loads(trace.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("original Core trace is unreadable") from exc
    scenes = original.get("scenes") if isinstance(original, dict) else None
    if not isinstance(scenes, list) or len(scenes) != frames_declared:
        raise EvidenceError("complete original Core scene history is missing")
    timestamps = []
    for scene in scenes:
        stamp = scene.get("t") if isinstance(scene, dict) else None
        if isinstance(stamp, bool) or not isinstance(stamp, int):
            raise EvidenceError("original Core scene timestamp is missing")
        if timestamps and stamp <= timestamps[-1]:
            raise EvidenceError("original Core scene timestamps must increase")
        timestamps.append(stamp)
    for sample in samples:
        frame = sample["frame"]
        if frame >= len(timestamps) or timestamps[frame] != round(sample["time_s"] * 1000):
            raise EvidenceError("signal sample/Core timestamp join failed")
    return {"scene_count": len(timestamps), "first_timestamp_ms": timestamps[0],
            "last_timestamp_ms": timestamps[-1], "joined_signal_samples": len(samples)}


def review(repo: Path, recording_id: str, trace: Path, video: Path,
           packet_path: Path, source_root: Path) -> dict:
    admission = verify_accepted(repo, recording_id, trace, video)
    packet_hash = verify_packet_binding(repo, recording_id, packet_path)
    packet = json.loads(packet_path.read_text())
    if packet.get("case_id") != admission["case_id"]:
        raise EvidenceError("signal packet differs from accepted case identity")
    suffix = admission["case_id"].rsplit("__", 1)[-1]
    if packet.get("turn_direction") != "left":
        raise EvidenceError("frozen C178244 left-turn direction differs")
    if packet.get("district_class") != DISTRICT_FROM_CASE[suffix]:
        raise EvidenceError("district differs from frozen case identity")
    if packet.get("duration_frames") != admission["frames_declared"]:
        raise EvidenceError("signal packet duration differs from accepted recording")
    for key, accepted in (("original_trace_sha256", admission["trace_sha256"]),
                          ("original_video_sha256", admission["video_sha256"])):
        if packet.get(key) != accepted:
            raise EvidenceError(f"signal packet {key} differs from accepted recording")
    bound = verify_source_bindings(packet, source_root)
    measurement = measure(packet)
    core_time_join = verify_core_time_join(trace, admission["frames_declared"], packet["samples"])
    return {
        "format": "accepted-signal-distance-review",
        "assignment_id": admission["assignment_id"],
        "recording_id": recording_id,
        "case_id": admission["case_id"],
        "admission": admission,
        "packet_source_sha256": packet_hash,
        "signal_sources_verified": bound,
        "core_time_join": core_time_join,
        "measurement": measurement,
        "finding": "source-bound physical distance measurement; district applicability and legal compliance remain independent review questions",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.repo.resolve(), args.recording_id, args.trace,
                            args.video, args.packet, args.source_root), sort_keys=True))


if __name__ == "__main__":
    main()
