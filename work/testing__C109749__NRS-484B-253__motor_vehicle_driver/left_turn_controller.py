"""Deterministic left-turn request policy, separate from measured behavior.

The caller drives this policy once per 20 Hz Native tick using actual body
occupancy and clearance events.  It returns path/speed targets, never a legal
yield conclusion.  A downstream controller must track those targets and retain
the actual controls and body histories.
"""

from dataclasses import dataclass


@dataclass
class TurnPolicy:
    wait_for_initial_opponent: bool
    signal_left: bool
    wait_for_later_opponent: bool | None = None
    phase: str = "approach"

    def tick(self, *, ego_fully_inside, initial_opponent_cleared,
             later_opponent_present, left_route_connected, speed_mps):
        if not left_route_connected:
            raise ValueError("native map has no connected left-turn route")
        if not isinstance(ego_fully_inside, bool) or not isinstance(initial_opponent_cleared, bool):
            raise ValueError("original body occupancy and clearance flags required")
        if speed_mps < 0:
            raise ValueError("speed target must be nonnegative")
        if self.phase == "approach" and ego_fully_inside:
            self.phase = "wait" if self.wait_for_initial_opponent else "turn"
        if self.phase == "wait" and initial_opponent_cleared:
            self.phase = "turn"
        if self.phase == "turn" and self.wait_for_later_opponent and later_opponent_present:
            self.phase = "later_wait"
        if self.phase == "later_wait" and not later_opponent_present:
            self.phase = "turn"
        return {"phase": self.phase, "left_signal_requested": self.signal_left,
                "target_speed_mps": 0.0 if self.phase in ("wait", "later_wait") else float(speed_mps),
                "path_request": "left_turn" if self.phase == "turn" else "approach_or_hold",
                "measured_behavior": None}
