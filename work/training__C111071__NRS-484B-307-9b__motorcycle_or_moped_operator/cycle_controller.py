"""C111071 proposed straight-route gate from observed signal and body samples.

This is a CPU controller component, not a Native signal observation or a legal
decision. Complete cycles are counted from phase transitions, never from a
fixture-provided cycle count. A local Native runner must feed original samples.
"""
from __future__ import annotations

from dataclasses import dataclass


RATE_HZ = 20
FRAMES = 600
EGO_FACE = "circular_red_green_left_arrow"
PHASES = ("cross_green", "cross_yellow", "cross_red")


@dataclass(frozen=True)
class Sample:
    frame: int
    ego_face: str
    cross_phase: str
    ego_speed_mps: float
    front_to_stop_m: float
    entered_intersection: bool
    detector_request_present: bool
    detector_request_serviced: bool
    pedestrians_in_crosswalk: bool
    lawful_traffic_conflict: bool


def measure(samples: list[Sample]) -> dict:
    if len(samples) != FRAMES:
        raise ValueError("exact 600-frame measurement required")
    if [s.frame for s in samples] != list(range(FRAMES)):
        raise ValueError("nonsequential frame identity")
    if any(s.ego_face != EGO_FACE or s.cross_phase not in PHASES for s in samples):
        raise ValueError("missing steady red/green arrow or phase source")
    if any(s.ego_speed_mps < 0 or s.front_to_stop_m != s.front_to_stop_m for s in samples):
        raise ValueError("invalid body measurement")
    stop_frames = [s.frame for s in samples if s.ego_speed_mps <= 0.05 and s.front_to_stop_m >= 0]
    stop_start = None
    for frame in stop_frames:
        if all(k in stop_frames for k in range(frame, frame + 10)):
            stop_start = frame
            break
    if stop_start is None:
        raise ValueError("no ten-frame complete halt before stop boundary")
    # A complete cycle starts and ends on the same phase with all other phases
    # visited in between. Count only cycles completed after the measured halt.
    initial = samples[stop_start].cross_phase
    visited: set[str] = set()
    cycle_end_frames: list[int] = []
    prior = initial
    for s in samples[stop_start + 1:]:
        phase = s.cross_phase
        if phase != prior:
            if phase == initial and visited == set(PHASES) - {initial}:
                cycle_end_frames.append(s.frame)
                visited.clear()
            elif phase != initial:
                visited.add(phase)
            else:
                visited.clear()
        prior = phase
    entry_frames = [s.frame for s in samples if s.entered_intersection]
    entry = min(entry_frames) if entry_frames else None
    if entry is not None and any(not s.entered_intersection for s in samples[entry + 1:]):
        raise ValueError("nonmonotone intersection entry")
    entry_sample = samples[entry] if entry is not None else None
    two_cycles_before_entry = bool(entry is not None and len([f for f in cycle_end_frames if f < entry]) >= 2)
    detector_failure_trace = all(s.detector_request_present and not s.detector_request_serviced
                                 for s in samples[stop_start:(entry or FRAMES)])
    yield_clear_at_entry = bool(entry_sample and not entry_sample.pedestrians_in_crosswalk
                                and not entry_sample.lawful_traffic_conflict)
    return {
        "frame_rate_hz": RATE_HZ,
        "frame_count": FRAMES,
        "stop_start_frame": stop_start,
        "complete_cycle_end_frames": cycle_end_frames,
        "entry_frame": entry,
        "two_cycles_before_entry": two_cycles_before_entry,
        "detector_failure_command_trace": detector_failure_trace,
        "yield_clear_at_entry": yield_clear_at_entry,
        "requested_gate_satisfied": bool(two_cycles_before_entry and detector_failure_trace and yield_clear_at_entry),
        "scope": "synthetic source-shaped CPU diagnostic; Native source and physical causation unverified",
    }


def commanded_brake(sample: Sample, completed_cycles: int, target_cycles: int) -> float:
    """Post-tick command request; the next measured sample remains authoritative."""
    if target_cycles not in (1, 2):
        raise ValueError("target cycles must be one or two for the controlled pair")
    if sample.pedestrians_in_crosswalk or sample.lawful_traffic_conflict:
        return 1.0
    if sample.front_to_stop_m >= 0 and completed_cycles < target_cycles:
        return 1.0
    return 0.0
