"""Source-bound parked-headlamp measurements for NRS 484D.165(4).

Requested CARLA light bits are construction targets. Original light-state readback,
body motion, brake state and camera pixels are separate evidence. The reported
quantities do not decide whether a lamp legally counts as depressed or dimmed.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


CASE_MODES = ("unlit", "low_beam", "high_beam")


def command_lights(vehicle, light_state, mode: str):
    """Set a requested headlamp mode using an injected CARLA light enum.

    CARLA is deliberately not imported at module load. Readback is retained
    because a command alone cannot show the actual actor state.
    """
    if mode not in CASE_MODES:
        raise ValueError("unknown headlamp mode")
    state = light_state.NONE if mode == "unlit" else light_state.Position
    if mode == "low_beam":
        state |= light_state.LowBeam
    elif mode == "high_beam":
        state |= light_state.HighBeam
    vehicle.set_light_state(state)
    return {"requested_mode": mode, "requested_bits": int(state),
            "readback_bits": int(vehicle.get_light_state())}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path):
    if not path.is_file():
        raise ValueError("missing original source: " + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not rows:
        raise ValueError("empty original source: " + path.name)
    return rows


def measure(original_dir: Path, expected_hashes: dict[str, str], *, mode: str,
            low_beam_bit: int, high_beam_bit: int) -> dict:
    """Measure an original 20 Hz observation interval without a legal label.

    Required JSONL: actor-state with frame, time_s, speed_mps, parking_brake,
    footprint_inside_reviewed_parking_polygon, light_state_bits and actor_id;
    camera-frame-map with matching frame and source_frame for four original views.
    The polygon predicate must be calculated from Native body and reviewed map
    geometry by the capture writer, never copied from a requested case flag.
    """
    if mode not in CASE_MODES or low_beam_bit <= 0 or high_beam_bit <= 0:
        raise ValueError("invalid lamp measurement contract")
    if low_beam_bit & high_beam_bit:
        raise ValueError("low/high beam masks overlap")
    root = Path(original_dir)
    names = ("actor-state.jsonl", "camera-frame-map.jsonl")
    for name in names:
        if not (root / name).is_file() or expected_hashes.get(name) != _hash(root / name):
            raise ValueError("original source hash changed or missing: " + name)
    states, maps = (_rows(root / name) for name in names)
    if len(states) != len(maps) or len(states) < 2:
        raise ValueError("original frame/source length mismatch")
    frames = []
    parked = []
    low = []
    high = []
    actor_ids = set()
    for i, (state, mapped) in enumerate(zip(states, maps)):
        frame = state.get("frame")
        if type(frame) is not int or frame != states[0].get("frame") + i or mapped.get("frame") != frame:
            raise ValueError("original frame join is not contiguous")
        if not all(type(mapped.get(view)) is int for view in
                   ("overview_source_frame", "approach_source_frame",
                    "reference_corner_source_frame", "driver_reference_source_frame")):
            raise ValueError("missing original four-view frame map")
        t = state.get("time_s")
        if type(t) not in (int, float) or not math.isfinite(t):
            raise ValueError("invalid original time")
        if i and abs((t - states[i - 1]["time_s"]) - .05) > .01:
            raise ValueError("original time is not 20 Hz")
        speed = state.get("speed_mps")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("invalid original speed")
        bits = state.get("light_state_bits")
        if type(bits) is not int:
            raise ValueError("missing original light-state readback")
        if type(state.get("parking_brake")) is not bool or type(state.get("footprint_inside_reviewed_parking_polygon")) is not bool:
            raise ValueError("parking evidence must be measured and boolean")
        actor_ids.add(state.get("actor_id"))
        frames.append(frame)
        parked.append(speed <= .1 and state["parking_brake"] and state["footprint_inside_reviewed_parking_polygon"])
        low.append(bool(bits & low_beam_bit))
        high.append(bool(bits & high_beam_bit))
    if len(actor_ids) != 1 or None in actor_ids:
        raise ValueError("original actor identity changes")
    return {"format": "parked-headlamp-original-measurement-v1", "requested_mode": mode,
            "actor_id": next(iter(actor_ids)), "frame_count": len(frames),
            "first_original_frame": frames[0], "last_original_frame": frames[-1],
            "parked_sample_count": sum(parked), "low_beam_readback_count": sum(low),
            "high_beam_readback_count": sum(high),
            "source_hashes": {name: expected_hashes[name] for name in names},
            "unresolved": ["Actual lamp emission and beam aim require original camera review.",
                           "Parked status and statutory dimmed/depressed meaning require independent review."]}
