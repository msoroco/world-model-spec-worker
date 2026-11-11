"""Join source-bound signal telemetry to measured intersection entries.

The output describes Native state at each entry. It does not equate an Off
simulation state with the statutory inoperative condition or issue a verdict.
"""

import hashlib
import json
import math
from pathlib import Path


REQUIRED = ("signal_history.jsonl", "video_frames.jsonl", "signal_context.json")
VALID_STATES = {"Red", "Yellow", "Green", "Off", "Unknown"}


def _read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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
    for key in ("native_signal_id", "native_map_id", "governed_road_id", "governed_lane_id"):
        if context.get(key) is None:
            raise ValueError("Missing Native signal provenance: " + key)
    if context.get("vehicular_heads_installed") is not True or context.get("vehicular_heads_uncovered") is not True:
        raise ValueError("Installed uncovered signal heads lack source evidence")
    if not context.get("head_visibility_source"):
        raise ValueError("Missing visible head source")
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
        if row.get("native_signal_id") != context["native_signal_id"] or row.get("state") not in VALID_STATES:
            raise ValueError("Signal identity or Native state invalid")
        by_frame[identity[0]] = row
    at_entry = {}
    for party, entry in entry_measurements.get("first_body_entry", {}).items():
        if entry is None:
            at_entry[party] = None
            continue
        row = by_frame.get(entry.get("frame"))
        if row is None or row["time_s"] != entry.get("time_s"):
            raise ValueError("No signal state at measured body entry")
        at_entry[party] = {"frame": row["frame"], "time_s": row["time_s"], "native_state": row["state"]}
    if set(at_entry) != {"ego", "other"}:
        raise ValueError("Both vehicle entries required")
    return {
        "format": "worker-native-signal-at-entry",
        "sources": sources,
        "signal_context": context,
        "at_body_entry": at_entry,
        "official_control_judgment": "unresolved; Native actor/state alone does not establish official status",
        "inoperative_judgment": "unresolved; Off is a simulation observation, not a statutory conclusion",
    }
