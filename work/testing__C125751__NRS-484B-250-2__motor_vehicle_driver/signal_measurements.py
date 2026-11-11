"""Join source-bound signal telemetry to measured intersection entries.

The output describes Native state at each entry. It does not equate an Off
simulation state with the statutory inoperative condition or issue a verdict.
"""

import hashlib
import json
import math
from pathlib import Path


REQUIRED = ("signal_history.jsonl", "video_frames.jsonl", "signal_context.json",
            "head_visibility_review.json", "other_head_visibility_review.json")
VALID_STATES = {"Red", "Yellow", "Green", "Off", "Unknown"}
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def _read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _head_review(root, name, identity, frames):
    review = json.loads((root / name).read_text())
    camera = review.get("camera")
    if camera not in CAMERAS or review.get("native_signal_id") != identity:
        raise ValueError("Reviewed source camera/signal identity missing")
    video = root / (camera + ".mkv")
    if not video.is_file() or hashlib.sha256(video.read_bytes()).hexdigest() != review.get("source_video_sha256"):
        raise ValueError("Head review is not bound to retained source video")
    index = review.get("video_frame")
    if type(index) is not int or not 0 <= index < len(frames) or review.get("carla_frame") != frames[index]["carla_frame"]:
        raise ValueError("Head review frame does not join original source")
    region = review.get("head_region_px")
    if not isinstance(region, list) or len(region) != 4 or any(type(v) is not int or v < 0 for v in region) or region[2] <= region[0] or region[3] <= region[1]:
        raise ValueError("Head review lacks positive pixel region")
    if review.get("installed") is not True or review.get("uncovered") is not True or not review.get("review_basis"):
        raise ValueError("Installed uncovered signal heads lack source review")
    return {"camera": camera, "video_frame": index, "carla_frame": review["carla_frame"],
            "head_region_px": region, "review_basis": review["review_basis"]}, review["source_video_sha256"]


def analyze(root: Path, entry_measurements: dict) -> dict:
    root = Path(root)
    sources = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required signal source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "signal_context.json").read_text())
    if context.get("intersection_id") != entry_measurements.get("intersection_id"):
        raise ValueError("Signal and entry intersection identities differ")
    for key in ("native_signal_id", "other_native_signal_id", "native_map_id", "governed_road_id",
                "governed_lane_id", "other_governed_road_id", "other_governed_lane_id"):
        if context.get(key) is None:
            raise ValueError("Missing Native signal provenance: " + key)
    if context["native_signal_id"] == context["other_native_signal_id"]:
        raise ValueError("Distinct governing signals required for two approaches")
    rows = _read_rows(root / "signal_history.jsonl")
    frames = _read_rows(root / "video_frames.jsonl")
    if not rows or len(rows) != len(frames):
        raise ValueError("Incomplete signal/frame history")
    by_frame = {}
    previous = (-1, -math.inf)
    for index, (row, frame) in enumerate(zip(rows, frames)):
        identity = (row.get("frame"), row.get("time_s"))
        if type(identity[0]) is not int or not isinstance(identity[1], (int, float)) or isinstance(identity[1], bool) or not math.isfinite(identity[1]) or identity[0] <= previous[0] or identity[1] <= previous[1]:
            raise ValueError("Nonmonotone signal history")
        previous = identity
        if frame.get("video_frame") != index or frame.get("carla_frame") != identity[0] or frame.get("time_s") != identity[1]:
            raise ValueError("Original signal/frame join failed")
        if (row.get("native_signal_id") != context["native_signal_id"] or row.get("state") not in VALID_STATES
                or row.get("other_native_signal_id") != context["other_native_signal_id"]
                or row.get("other_state") not in VALID_STATES):
            raise ValueError("Signal identity or Native state invalid")
        by_frame[identity[0]] = row
    review, video_sha = _head_review(root, "head_visibility_review.json", context["native_signal_id"], frames)
    other_review, other_video_sha = _head_review(root, "other_head_visibility_review.json",
                                                  context["other_native_signal_id"], frames)
    at_entry = {}
    for party, entry in entry_measurements.get("first_body_entry", {}).items():
        if entry is None:
            at_entry[party] = None
            continue
        row = by_frame.get(entry.get("frame"))
        if row is None or row["time_s"] != entry.get("time_s"):
            raise ValueError("No signal state at measured body entry")
        state_key = "state" if party == "ego" else "other_state"
        id_key = "native_signal_id" if party == "ego" else "other_native_signal_id"
        at_entry[party] = {"frame": row["frame"], "time_s": row["time_s"],
                           "native_state": row[state_key], "native_signal_id": row[id_key]}
    if set(at_entry) != {"ego", "other"}:
        raise ValueError("Both vehicle entries required")
    return {
        "format": "worker-native-signal-at-entry",
        "sources": sources,
        "source_video_sha256": video_sha,
        "other_source_video_sha256": other_video_sha,
        "head_review": review, "other_head_review": other_review,
        "signal_context": context,
        "at_body_entry": at_entry,
        "official_control_judgment": "unresolved; Native actor/state alone does not establish official status",
        "inoperative_judgment": "unresolved; Off is a simulation observation, not a statutory conclusion",
    }
