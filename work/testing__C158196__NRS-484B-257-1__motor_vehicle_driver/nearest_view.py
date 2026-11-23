"""Source-gated measurement for the yield sign's nearest-view branch.

Inputs are original-tick observations, not commanded speeds or legal findings.
The runner must obtain the context from Native map/device/readback sources.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


REQUIRED_SOURCES = (
    "native_map", "yield_sign_readback", "signal_state_readback",
    "officer_observation", "stop_line_survey", "crosswalk_survey",
    "sidewalk_survey", "through_highway_survey", "view_raycast",
)


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _source(item: object, name: str) -> None:
    if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"]:
        raise ValueError(f"{name} source path missing")
    digest = item.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError(f"{name} source hash missing")


def verify_source_bytes(packet: dict, packet_dir: Path) -> None:
    """Bind each declared original source to bytes inside the saved attempt."""
    base = packet_dir.resolve()
    for name in REQUIRED_SOURCES:
        item = packet["sources"].get(name)
        _source(item, name)
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"{name} source escapes attempt")
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise ValueError(f"{name} source bytes missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"{name} source hash mismatch")


def measure(packet: dict) -> dict:
    """Measure observed ordering and conflict interval; leave legal judgment open."""
    context = packet["context"]
    sources = packet["sources"]
    for name in REQUIRED_SOURCES:
        _source(sources.get(name), name)
    if context.get("cell_id") != "C158196" or context.get("law_id") != "NRS-484B-257-1":
        raise ValueError("wrong exact cell or law")
    required_true = ("proper_yield_sign", "through_highway", "connected_approach")
    required_false = ("marked_stop_line", "near_side_crosswalk", "sidewalk_derived_crosswalk",
                      "officer_controlling", "signal_controlling")
    for name in required_true:
        if context.get(name) is not True:
            raise ValueError(f"{name} not source-confirmed")
    for name in required_false:
        if context.get(name) is not False:
            raise ValueError(f"{name} must be source-confirmed absent")
    view_station = _number(context.get("nearest_view_station_m"), "nearest_view_station_m")
    entry_station = _number(context.get("intersection_entry_station_m"), "intersection_entry_station_m")
    if view_station >= entry_station:
        raise ValueError("nearest-view point must precede intersection entry")
    frames = packet["frames"]
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("original frame history too short")
    first = frames[0]
    base_frame = first.get("frame")
    base_time = _number(first.get("time_s"), "time_s")
    if not isinstance(base_frame, int) or isinstance(base_frame, bool):
        raise ValueError("original frame number missing")
    first_view = None
    first_entry = None
    crossing = []
    prior_front = None
    for i, item in enumerate(frames):
        if item.get("frame") != base_frame + i:
            raise ValueError("original frames not contiguous")
        if abs(_number(item.get("time_s"), "time_s") - (base_time + i / 20)) > 0.001:
            raise ValueError("original timestamps not 20 Hz")
        front = _number(item.get("ego_front_station_m"), "ego_front_station_m")
        speed = _number(item.get("ego_speed_mps"), "ego_speed_mps")
        through = _number(item.get("through_center_station_m"), "through_center_station_m")
        if speed < 0:
            raise ValueError("negative physical speed")
        for key in ("view_clear", "through_occupied", "ego_within_intersection"):
            if not isinstance(item.get(key), bool):
                raise ValueError(f"{key} original observation missing")
        if prior_front is not None and front < prior_front - 0.2:
            raise ValueError("ego approach reversed beyond measurement tolerance")
        prior_front = front
        if first_view is None and front >= view_station and item["view_clear"]:
            first_view = i
        if first_entry is None and front >= entry_station:
            first_entry = i
        if item["ego_within_intersection"]:
            crossing.append(i)
    if first_view is None or first_entry is None or first_view >= first_entry:
        raise ValueError("observed view must precede actual entry")
    if not crossing or crossing[0] < first_entry:
        raise ValueError("crossing history missing or precedes entry")
    approach = frames[:first_entry + 1]
    return {
        "first_view_frame": frames[first_view]["frame"],
        "first_entry_frame": frames[first_entry]["frame"],
        "minimum_approach_speed_mps": min(x["ego_speed_mps"] for x in approach),
        "through_center_at_view_m": frames[first_view]["through_center_station_m"],
        "through_occupied_during_crossing": any(frames[i]["through_occupied"] for i in crossing),
        "crossing_frame_count": len(crossing),
        "legal_immediate_hazard": "unresolved_judgment",
        "legal_right_of_way": "unresolved_judgment",
    }


def compare(left: dict, right: dict, *, differing: tuple[str, ...]) -> dict:
    """Reject undeclared context changes and measure both original histories."""
    allowed = set(differing)
    for key in set(left["context"]) | set(right["context"]):
        if key not in allowed and left["context"].get(key) != right["context"].get(key):
            raise ValueError(f"unreviewed fixed-condition change: {key}")
    measured = [measure(left), measure(right)]
    return {"left": measured[0], "right": measured[1],
            "declared_differences": sorted(allowed), "comparison_status": "measured_not_legal_verdict"}


def main(path: Path, output: Path) -> None:
    raw = path.read_bytes()
    packet = json.loads(raw)
    verify_source_bytes(packet, path.parent)
    measured = measure(packet)
    output.write_text(json.dumps({"input_sha256": hashlib.sha256(raw).hexdigest(),
                                  "measurement": measured}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    main(args.packet, args.output)
