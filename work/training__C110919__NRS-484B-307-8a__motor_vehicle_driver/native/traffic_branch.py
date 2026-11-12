"""Deterministic cross-traffic control contrast after the common red stop."""
from dataclasses import dataclass

POLICIES = ("traffic_yield_wait", "traffic_conflict_entry")


@dataclass(frozen=True)
class TrafficDecision:
    brake: bool
    clear_frames: int
    reason: str


def decide(policy, *, red_stop_completed, in_merge_approach,
           traffic_conflict_occupied, previous_clear_frames,
           required_clear_frames):
    if policy not in POLICIES:
        raise ValueError("Unknown cross-traffic policy")
    if any(type(value) is not bool for value in
           (red_stop_completed, in_merge_approach, traffic_conflict_occupied)):
        raise ValueError("Observed traffic state must be Boolean")
    if any(type(value) is not int or value < 0 for value in
           (previous_clear_frames, required_clear_frames)):
        raise ValueError("Clearance frames must be nonnegative integers")
    if not red_stop_completed:
        return TrafficDecision(True, 0, "red_stop_not_completed")
    if not in_merge_approach:
        return TrafficDecision(False, 0, "outside_merge_approach")
    if traffic_conflict_occupied:
        if policy == "traffic_yield_wait":
            return TrafficDecision(True, 0, "signal_directed_traffic_occupied")
        return TrafficDecision(False, 0, "deliberate_traffic_conflict_probe")
    clear = previous_clear_frames + 1
    if policy == "traffic_yield_wait" and clear < required_clear_frames:
        return TrafficDecision(True, clear, "traffic_clearance_pending")
    return TrafficDecision(False, clear, "traffic_conflict_clear")
