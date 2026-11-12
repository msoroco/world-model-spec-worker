"""Executable pedestrian-conflict branch for the C110919 right-turn proposal.

This is an engineering control comparison, not a legal right-of-way verdict.
The two branches share the same observed conflict occupancy and stopped ego.
"""
from __future__ import annotations

from dataclasses import dataclass


POLICIES = ("yield_wait", "yield_conflict_entry")


@dataclass(frozen=True)
class YieldDecision:
    brake: bool
    clearance_frames: int
    reason: str


def decide(policy: str, *, red_stop_completed: bool, in_turn_approach: bool,
           conflict_occupied: bool, previous_clearance_frames: int,
           required_clearance_frames: int) -> YieldDecision:
    """Return a deterministic command from observed actor state at 20 Hz.

    The contrast deliberately ignores a pedestrian in the conflict zone only
    after the shared red-signal stop. It must never bypass the stop obligation.
    """
    if policy not in POLICIES:
        raise ValueError("Unknown pedestrian-yield policy")
    if type(red_stop_completed) is not bool or type(in_turn_approach) is not bool or type(conflict_occupied) is not bool:
        raise ValueError("Observed state must be Boolean")
    if (type(previous_clearance_frames) is not int or previous_clearance_frames < 0 or
            type(required_clearance_frames) is not int or required_clearance_frames < 0):
        raise ValueError("Clearance frames must be nonnegative integers")
    if not red_stop_completed:
        return YieldDecision(True, 0, "red_stop_not_completed")
    if not in_turn_approach:
        return YieldDecision(False, 0, "outside_turn_approach")
    if conflict_occupied:
        if policy == "yield_wait":
            return YieldDecision(True, 0, "pedestrian_conflict_occupied")
        return YieldDecision(False, 0, "deliberate_conflict_entry_probe")
    clearance = previous_clearance_frames + 1
    if policy == "yield_wait" and clearance < required_clearance_frames:
        return YieldDecision(True, clearance, "clearance_margin_pending")
    return YieldDecision(False, clearance, "conflict_clear")
