"""Independent saved-source checks for the exit interaction package."""
from __future__ import annotations

from typing import Mapping


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_saved(packet: Mapping) -> dict:
    """Inspect sealed references. A local accepted recording still needs review."""
    require(packet.get("case_id"), "case identity missing")
    require(packet.get("native_result_sha256") and packet.get("original_history_sha256"), "sealed Native sources missing")
    require(packet.get("frame_count") == 900, "complete original frame history missing")
    frames = packet.get("frame_map", [])
    require(len(frames) == 900, "original frame map missing")
    first = frames[0].get("original_frame")
    require(type(first) is int, "first original frame missing")
    for index, frame in enumerate(frames):
        require(frame.get("original_frame") == first + index, "original frame map discontinuous")
        require(abs(frame.get("elapsed_s", -1) - index * .05) <= .001, "original frame time mismatch")
    videos = packet.get("videos", {})
    require(set(videos) == {"chase", "overhead", "front", "side"}, "four original cameras required")
    for name, video in videos.items():
        require(video.get("sha256") and video.get("decode_receipt_sha256"), f"camera source missing: {name}")
        require(video.get("decoded_frame_count") == 900, f"full camera decode missing: {name}")
        require(video.get("actual_pixel_audit") is True, f"actual pixel audit missing: {name}")
        require(video.get("first_original_frame") == first and video.get("last_original_frame") == first + 899, f"camera alignment mismatch: {name}")
    measurement = packet.get("measurement", {})
    require(measurement.get("case_id") == packet["case_id"] and measurement.get("frame_count") == 900, "case-specific measurement missing")
    require(measurement.get("source_history_sha256") == packet["original_history_sha256"], "measurement source mismatch")
    require(measurement.get("first_entry_frame") is not None, "exit interaction completion missing")
    require(measurement.get("approaching_actor_ids"), "approaching vehicles missing")
    require(measurement.get("immediate_hazard_judgment") is None and measurement.get("reasonable_safety_judgment") is None,
            "worker may not assert legal judgment")
    return {"case_id": packet["case_id"], "frame_count": 900, "first_original_frame": first,
            "last_original_frame": first + 899, "source_bound": True, "legal_judgment": None}
