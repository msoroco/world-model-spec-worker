"""Source-bound original-frame measurement for NRS 484B.307(6)(a).

This module does not decide legality. It requires a surveyed intersection entry
surface and an official device-to-route binding supplied by a Native capture.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class Crossing:
    before_frame: int
    after_frame: int
    before_time_s: float
    after_time_s: float
    signal_before: str
    signal_after: str


def _required_source(value: Any, label: str) -> None:
    if not isinstance(value, dict) or not value.get("path") or not value.get("sha256"):
        raise EvidenceError(f"missing {label} source binding")
    if len(value["sha256"]) != 64:
        raise EvidenceError(f"invalid {label} source hash")


def _selected_signal(frame: dict, route_id: str, signal_id: str,
                     allow_companion: bool = False) -> dict:
    signals = frame.get("signals")
    if not isinstance(signals, list):
        raise EvidenceError("missing original signal readback")
    matches = [s for s in signals if s.get("signal_id") == signal_id and s.get("route_id") == route_id]
    if len(matches) != 1:
        raise EvidenceError("selected route must have exactly one bound signal")
    signal = matches[0]
    if signal.get("kind") != "vehicular" or signal.get("official") is not True or signal.get("facing_ego") is not True:
        raise EvidenceError("selected official facing vehicular signal unverified")
    if signal.get("state") not in {"green", "yellow", "red"}:
        raise EvidenceError("unknown selected signal indication")
    if signal.get("state") == "yellow":
        if signal.get("flashing") is not False:
            raise EvidenceError("steady yellow alone unverified")
        companions = signal.get("companion_lamps_on")
        if not isinstance(companions, list) or (companions and not allow_companion):
            raise EvidenceError("steady yellow alone unverified")
        if companions and not all(isinstance(lamp, str) and lamp for lamp in companions):
            raise EvidenceError("companion indication readback invalid")
    _required_source(signal.get("source"), "selected signal")
    return signal


def measure(packet: dict, expected_frames: int = 900,
            case_profile: str = "steady_yellow_alone") -> dict:
    """Measure phase sequence and entry bracket from a sealed Native packet."""
    for label in ("intersection_polygon", "route_connectivity", "device_route_binding", "native_result"):
        _required_source(packet.get(label), label)
    if packet.get("layout") != "one_way_to_two_way_intersection":
        raise EvidenceError("wrong intersection layout")
    route_id, signal_id = packet.get("route_id"), packet.get("signal_id")
    if not route_id or not signal_id:
        raise EvidenceError("missing selected route or device")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != expected_frames:
        raise EvidenceError("incomplete original frame history")
    if case_profile not in ("steady_yellow_alone", "yellow_non_alone", "red_other_route"):
        raise EvidenceError("unknown signal case profile")
    states = []
    distances = []
    companion_frames = []
    other_route_red_frames = []
    for i, frame in enumerate(frames):
        if frame.get("frame") != i or abs(frame.get("time_s", -999) - i / 20.0) > 0.001:
            raise EvidenceError("broken original 20 Hz frame/time join")
        if frame.get("source_frame") is None or frame.get("source_frame") != i:
            raise EvidenceError("missing original source frame identity")
        distance = frame.get("ego_front_signed_distance_m")
        if not isinstance(distance, (int, float)) or isinstance(distance, bool):
            raise EvidenceError("missing original front-to-entry geometry")
        _required_source(frame.get("ego_geometry_source"), "ego geometry")
        distances.append(float(distance))
        selected = _selected_signal(frame, route_id, signal_id,
                                    allow_companion=case_profile == "yellow_non_alone")
        states.append(selected["state"])
        if selected["state"] == "yellow" and selected["companion_lamps_on"]:
            companion_frames.append(i)
        if case_profile == "red_other_route":
            other = [lamp for lamp in frame["signals"]
                     if lamp.get("route_id") != route_id and lamp.get("signal_id") != signal_id
                     and lamp.get("kind") == "vehicular" and lamp.get("official") is True
                     and lamp.get("state") == "red"]
            for lamp in other:
                _required_source(lamp.get("source"), "other-route signal")
            if other:
                other_route_red_frames.append(i)
    if case_profile == "yellow_non_alone" and not companion_frames:
        raise EvidenceError("companion indication not observed")
    if case_profile == "red_other_route" and not other_route_red_frames:
        raise EvidenceError("other-route red indication not observed")
    transitions = [(i, states[i - 1], states[i]) for i in range(1, len(states)) if states[i] != states[i - 1]]
    allowed = {("green", "yellow"), ("yellow", "red")}
    if any((a, b) not in allowed for _, a, b in transitions):
        raise EvidenceError("selected signal sequence is not green-yellow-red")
    if not any(a == "green" and b == "yellow" for _, a, b in transitions):
        raise EvidenceError("missing related green termination")
    if not any(a == "yellow" and b == "red" for _, a, b in transitions):
        raise EvidenceError("missing subsequent red exhibition")
    crossings = [Crossing(i - 1, i, (i - 1) / 20, i / 20, states[i - 1], states[i])
                 for i in range(1, len(distances)) if distances[i - 1] < 0 <= distances[i]]
    if len(crossings) > 1:
        raise EvidenceError("multiple intersection entries require separate review")
    crossing = crossings[0].__dict__ if crossings else None
    if case_profile == "red_other_route" and (crossing is None or
        crossing["after_frame"] not in other_route_red_frames or
        crossing["signal_after"] == "red"):
        raise EvidenceError("other-route red did not contrast with selected entry")
    initially_inside = distances[0] >= 0
    return {
        "format": "original-signal-entry-measurement",
        "source_native_result": packet["native_result"],
        "selected_route_id": route_id,
        "selected_signal_id": signal_id,
        "frame_count": len(frames),
        "phase_transitions": [{"before_frame": i - 1, "after_frame": i, "from": a, "to": b} for i, a, b in transitions],
        "initially_inside_intersection": initially_inside,
        "yellow_alone_observed": bool(any(state == "yellow" for state in states) and
                                      not companion_frames),
        "companion_indication_frames": companion_frames,
        "other_route_red_frames": other_route_red_frames,
        "entry_bracket": crossing,
        "entry_observation": ("already_inside_at_capture_start" if initially_inside else "no_entry")
        if crossing is None else (
            "red_both_samples" if crossing["signal_before"] == crossing["signal_after"] == "red" else
            "yellow_both_samples" if crossing["signal_before"] == crossing["signal_after"] == "yellow" else
            "transition_bracket_unresolved"),
        "legal_judgment": "unresolved",
    }
