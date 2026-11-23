"""Independent saved-source checks for C150979; no legal or physical verdict."""

import hashlib
from pathlib import Path


CAMERAS = ("front", "rear", "left", "right")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_saved(source, measured):
    """Require current, complete original acquisition joins and real media bytes.

    Caller supplies sealed Native paths/claims after acquisition; the auditor
    opens each file itself. Decode counts are claimed by the caller and require
    separate full video decoder receipts; this check cannot establish pixels.
    """
    _require(source.get("case_id") == measured.get("case_id"), "case binding missing")
    _require(source.get("native_result_path") and source.get("native_result_sha256"), "sealed Native result missing")
    _require(file_sha256(source["native_result_path"]) == source["native_result_sha256"], "Native result seal mismatch")
    _require(source.get("map_sha256") == measured.get("map_sha256"), "map join mismatch")
    count = measured.get("original_frame_count")
    _require(isinstance(count, int) and count >= 400, "original frame count missing")
    frame_map = source.get("frame_map")
    _require(isinstance(frame_map, list) and len(frame_map) == count, "frame map incomplete")
    for i, row in enumerate(frame_map):
        _require(row.get("frame_index") == i and row.get("native_frame") is not None and row.get("time_s") is not None, "frame map identity gap")
        if i:
            _require(row["native_frame"] > frame_map[i - 1]["native_frame"] and row["time_s"] > frame_map[i - 1]["time_s"], "frame map nonmonotone")
    for sample in measured.get("governed_original_samples", []):
        i = sample.get("frame_index")
        _require(isinstance(i, int) and 0 <= i < count and abs(frame_map[i]["time_s"] - sample.get("time_s", -1)) <= 0.002, "measurement time join missing")
    cameras = source.get("cameras", {})
    _require(set(cameras) == set(CAMERAS), "four camera sources missing")
    for name in CAMERAS:
        row = cameras[name]
        _require(row.get("path") and row.get("sha256") and row.get("decoded_frames") == count, f"{name} camera decode missing")
        _require(file_sha256(row["path"]) == row["sha256"], f"{name} camera source changed")
        _require(row.get("original_frame_first") == 0 and row.get("original_frame_last") == count - 1, f"{name} camera frame join missing")
    for name in ("sign_inventory_source", "title_review_source"):
        item = source.get(name, {})
        _require(item.get("path") and item.get("sha256"), "posting source seals missing")
        _require(file_sha256(item["path"]) == item["sha256"], "posting source seal mismatch")
    _require(source.get("physical_completion") is True, "physical completion unconfirmed")
    return {"case_id": measured["case_id"], "original_frame_count": count,
            "native_result_sha256": source["native_result_sha256"],
            "camera_sha256": {name: cameras[name]["sha256"] for name in CAMERAS},
            "status": "source_join_checked_pending_independent_pixel_and_legal_review"}
