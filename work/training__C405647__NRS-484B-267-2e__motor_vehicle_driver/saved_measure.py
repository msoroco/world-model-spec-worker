"""Saved original emergency-lane observations without a legal feasibility cutoff."""
import hashlib
import json
import math
from pathlib import Path

from road_geometry import ADJACENT_LANE, EMERGENCY_LANE, NONADJACENT_LANE
from source_review import join


COUNT = 600
RATE = 20
VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
          "driver_reference.mkv")


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def measure(folder, case_id, diagnostic=False):
    folder = Path(folder)
    source = join(folder, case_id, diagnostic=diagnostic)
    for name in (*VIDEOS, "video_frames.jsonl", "emergency-native.jsonl",
                 "lamp-pixel-review.json", "signal-pixel-review.json"):
        if not (folder / name).is_file():
            raise ValueError("Missing required source: " + name)
    frame_map = rows(folder / "video_frames.jsonl")
    trace = rows(folder / "emergency-native.jsonl")
    lamp = json.loads((folder / "lamp-pixel-review.json").read_text())
    signal = json.loads((folder / "signal-pixel-review.json").read_text())
    require(len(frame_map) == len(trace) == COUNT, "Full 600-frame join required")
    require(lamp.get("case_id") == signal.get("case_id") == case_id,
            "Pixel review case differs")
    for review in (lamp, signal):
        require(len(review.get("frames", [])) == COUNT,
                "Full original pixel review interval required")
        if not diagnostic:
            for name in VIDEOS:
                require(review.get("video_sha256", {}).get(name) == digest(folder / name),
                        "Pixel review video hash differs: " + name)
        require(review.get("review_kind") ==
                ("synthetic_diagnostic" if diagnostic else "original_native"),
                "Original pixel review required")
    active, adjacent, nonadjacent, emergency_speed, lamp_frames, signal_frames = [], [], [], [], [], []
    first_ego = first_emergency = None
    for i, (mapping, row, lamp_frame, signal_frame) in enumerate(
            zip(frame_map, trace, lamp["frames"], signal["frames"])):
        require(row.get("frame") == i and mapping.get("video_frame") == i,
                "Original frame sequence differs")
        native = row.get("native_frame")
        require(native is not None and mapping.get("native_frame") == native,
                "Native/frame-map identity differs")
        require(abs(row.get("t_s", -1) - i / RATE) < .06 and
                abs(mapping.get("time_s", mapping.get("t_s", -1)) - row["t_s"]) < .06,
                "Original frame time join differs")
        ego, emergency = row.get("ego", {}), row.get("emergency", {})
        first_ego = first_ego or ego.get("actor_id")
        first_emergency = first_emergency or emergency.get("actor_id")
        require(first_ego and first_emergency and first_ego != first_emergency and
                ego.get("actor_id") == first_ego and emergency.get("actor_id") == first_emergency,
                "Original participant identity differs")
        require(emergency.get("lane_id") == EMERGENCY_LANE and
                ego.get("lane_id") in (ADJACENT_LANE, NONADJACENT_LANE),
                "Original lane readback outside authored graph")
        speed = emergency.get("speed_mps")
        require(isinstance(speed, (int, float)) and math.isfinite(speed),
                "Emergency motion source missing")
        emergency_speed.append(speed)
        require(lamp_frame.get("frame") == signal_frame.get("frame") == i and
                type(lamp_frame.get("qualifying_flashes_visible")) is bool and
                type(signal_frame.get("hand_signal_visible")) is bool and
                type(signal_frame.get("officer_direction_visible")) is bool,
                "Original per-frame pixel review incomplete")
        lamp_frames.append(lamp_frame["qualifying_flashes_visible"])
        signal_frames.append(signal_frame)
        approach = row.get("ego", {}).get("x_m", 0) < emergency.get("x_m", 0)
        moving = speed > .05
        preparation = signal_frame["hand_signal_visible"]
        if approach and lamp_frames[-1] and (moving or preparation):
            active.append(i)
            (adjacent if ego["lane_id"] == ADJACENT_LANE else nonadjacent).append(i)
    require(active, "No observed flashing moving-or-preparing approach interval")
    suffix = case_id[-2:]
    if suffix == "04":
        require(any(signal_frames[i]["hand_signal_visible"] for i in active),
                "Visible hand-signal preparation not established")
    if suffix == "05":
        require(any(signal_frames[i]["officer_direction_visible"] for i in active),
                "Officer direction not visible during approach")
    return {"format": "c405647-2e-saved-measurement-v1", "case_id": case_id,
            "source_join": source, "frame_count": COUNT, "duration_s": 30,
            "active_approach_frames": active, "active_adjacent_frames": adjacent,
            "active_nonadjacent_frames": nonadjacent,
            "moving_frames": [i for i, speed in enumerate(emergency_speed) if speed > .05],
            "visible_hand_signal_frames": [i for i, row in enumerate(signal_frames)
                                           if row["hand_signal_visible"]],
            "visible_officer_direction_frames": [i for i, row in enumerate(signal_frames)
                                                if row["officer_direction_visible"]],
            "motion_sensor_tolerance_mps": .05,
            "lane_change_possible": None, "lane_change_safe": None,
            "officer_override_applies": None, "legal_result": None,
            "physical_completion_verified": False,
            "source_sha256": {name: digest(folder / name) for name in
                              ("video_frames.jsonl", "emergency-native.jsonl",
                               "lamp-pixel-review.json", "signal-pixel-review.json")}}
