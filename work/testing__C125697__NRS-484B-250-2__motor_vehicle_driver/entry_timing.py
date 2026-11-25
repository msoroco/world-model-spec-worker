"""Source-bound original-frame observations for NRS 484B.250(2).

The output is evidence for later review, never a legal finding. In particular,
no numeric value here defines "approximately the same time".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry_bracket(frames: list[dict], actor: str) -> dict:
    before = None
    for frame in frames:
        state = frame["actors"][actor]
        inside = state["footprint_intersects_intersection"]
        _require(type(inside) is bool, f"{actor}: missing original footprint intersection boolean")
        if inside:
            _require(before is not None, f"{actor}: first original sample already intersects intersection")
            return {
                "lower_frame": before["frame"],
                "lower_timestamp_s": before["timestamp_s"],
                "upper_frame": frame["frame"],
                "upper_timestamp_s": frame["timestamp_s"],
            }
        before = frame
    raise ValueError(f"{actor}: no original footprint entry transition")


def measure(packet: dict) -> dict:
    """Measure entry timing from an unmodified, complete source-shaped packet."""
    _require(packet.get("format") == "nrs-484b-250-2-original-frames-v1", "wrong source format")
    _require(packet.get("law_id") == "NRS-484B-250-2", "wrong law")
    _require(packet.get("cell_id") == "C125697", "wrong cell")
    actors = packet.get("participants")
    _require(isinstance(actors, dict) and set(actors) == {"ego", "other"}, "two bound vehicle participants required")
    for name in ("ego", "other"):
        actor = actors[name]
        _require(actor.get("kind") == "motor_vehicle", f"{name}: vehicle kind required")
        _require(isinstance(actor.get("road_id"), str) and actor["road_id"], f"{name}: road ID required")
        _require(actor.get("approach_side") in {"left", "right"}, f"{name}: approach side required")
        _require(actor.get("movement") in {"straight", "left_turn", "right_turn"}, f"{name}: movement required")
    _require(actors["ego"]["road_id"] != actors["other"]["road_id"], "different highways not proven")
    _require({actors["ego"]["approach_side"], actors["other"]["approach_side"]} == {"left", "right"}, "left/right relationship not proven")
    _require(packet.get("opposite_approaches") is False, "opposite-approach exception unresolved")
    _require(packet.get("official_device_controls_intersection") is False, "official-device exception unresolved")
    device = packet.get("signal")
    _require(isinstance(device, dict) and device.get("present") is True and device.get("mode") == "inoperative", "inoperative signal readback required")
    _require(device.get("controls_traffic") is False, "inoperative control state not established")
    frames = packet.get("frames")
    _require(isinstance(frames, list) and len(frames) >= 3, "complete original frame history required")
    previous = None
    for frame in frames:
        idx, time = frame.get("frame"), frame.get("timestamp_s")
        _require(type(idx) is int and type(time) in (int, float) and math.isfinite(time), "invalid original frame identity/time")
        _require(isinstance(frame.get("actors"), dict) and set(frame["actors"]) == {"ego", "other"}, "participant state missing")
        if previous is not None:
            _require(idx == previous["frame"] + 1 and time > previous["timestamp_s"], "original frame sequence gap or time reversal")
        previous = frame
    ego = _entry_bracket(frames, "ego")
    other = _entry_bracket(frames, "other")
    difference = ego["upper_timestamp_s"] - other["upper_timestamp_s"]
    return {
        "format": "nrs-484b-250-2-entry-observation-v1",
        "law_id": packet["law_id"],
        "cell_id": packet["cell_id"],
        "case_id": packet.get("case_id"),
        "ego_entry": ego,
        "other_entry": other,
        "intersection_entry_time_difference_s": difference,
        "ego_approach_side": actors["ego"]["approach_side"],
        "other_approach_side": actors["other"]["approach_side"],
        "road_ids": {name: actors[name]["road_id"] for name in ("ego", "other")},
        "movements": {name: actors[name]["movement"] for name in ("ego", "other")},
        "signal": device,
        "opposite_approaches": packet["opposite_approaches"],
        "official_device_controls_intersection": packet["official_device_controls_intersection"],
        "source_frame_count": len(frames),
        "legal_judgment": None,
    }


def measure_file(path: Path, expected_sha256: str) -> dict:
    _require(_sha256(path) == expected_sha256, "source packet hash mismatch")
    observation = measure(json.loads(path.read_text(encoding="utf-8")))
    observation["source"] = {"path": str(path), "sha256": expected_sha256}
    return observation


def compare(observations: list[dict], planned_case_ids: list[str], variable: str) -> dict:
    """Audit case identity and one intended difference without a legal verdict."""
    _require(variable in {"entry_timing", "approach_side"}, "unsupported comparison variable")
    _require(len(observations) == len(planned_case_ids) and len(set(planned_case_ids)) == len(planned_case_ids), "comparison member count/identity invalid")
    _require([o.get("case_id") for o in observations] == planned_case_ids, "case identity mismatch")
    _require(all(o.get("format") == "nrs-484b-250-2-entry-observation-v1" and
                 isinstance(o.get("source"), dict) and
                 len(o["source"].get("sha256", "")) == 64 for o in observations),
             "source-bound observations required")
    _require(len({o["source"]["sha256"] for o in observations}) == len(observations),
             "comparison reuses the same original source")
    _require(all(o.get("law_id") == "NRS-484B-250-2" and o.get("cell_id") == "C125697" for o in observations), "comparison law/cell mismatch")
    for field in ("signal", "opposite_approaches", "official_device_controls_intersection"):
        _require(all(o.get(field) == observations[0].get(field) for o in observations), f"fixed condition changed: {field}")
    if variable == "entry_timing":
        for field in ("road_ids", "movements"):
            _require(all(o.get(field) == observations[0].get(field) for o in observations),
                     f"fixed condition changed: {field}")
        _require(len({o["ego_approach_side"] for o in observations}) == 1, "approach side changed in timing comparison")
        _require(len({o["intersection_entry_time_difference_s"] for o in observations}) == len(observations), "timing difference not observed")
    else:
        _require({o["ego_approach_side"] for o in observations} == {"left", "right"}, "left/right reversal not observed")
        _require(all(set(o["road_ids"].values()) == set(observations[0]["road_ids"].values())
                     for o in observations), "fixed crossing highways changed")
        _require(all(set(o["movements"].values()) == {"straight"} for o in observations),
                 "fixed straight movements changed")
        first = observations[0]["intersection_entry_time_difference_s"]
        _require(all(abs(o["intersection_entry_time_difference_s"] - first) <= .05
                     for o in observations), "fixed entry timing changed in side comparison")
    return {"format": "nrs-484b-250-2-comparison-audit-v1", "case_ids": planned_case_ids, "variable": variable, "source_hashes": [o["source"]["sha256"] for o in observations], "legal_judgment": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = measure_file(args.source, args.source_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
