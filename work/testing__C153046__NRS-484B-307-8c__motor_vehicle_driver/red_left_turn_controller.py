"""Source-aware engineering controller for a red-signal left-turn attempt.

This CPU policy requests motion only. It cannot establish statutory compliance,
signal authority, roadway classification, or realized yielding.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Observation:
    time_s: float
    distance_to_stop_boundary_m: float
    speed_m_s: float
    signal: str
    pedestrian_conflict: bool
    traffic_conflict: bool
    junction_exited: bool = False


class RedLeftTurnController:
    """Request approach, full stop, yield, then a left turn in that order."""

    def __init__(self, *, stop_dwell_s: float = 0.5, stop_speed_m_s: float = 0.05,
                 stop_request: str = "complete_stop", conflict_response_request: str = "yield"):
        if stop_dwell_s <= 0 or stop_speed_m_s <= 0:
            raise ValueError("positive engineering stop parameters required")
        if stop_request not in {"complete_stop", "rolling"} or conflict_response_request not in {
                "yield", "advance"}:
            raise ValueError("unknown exact controller request")
        self.stop_dwell_s = stop_dwell_s
        self.stop_speed_m_s = stop_speed_m_s
        self.stop_request = stop_request
        self.conflict_response_request = conflict_response_request
        self.phase = "approach"
        self.stop_start_s = None
        self.last_time_s = None
        self.history = []

    def step(self, observation: Observation) -> dict:
        if (any(type(value) not in (int, float) or not math.isfinite(value)
                for value in (observation.time_s, observation.distance_to_stop_boundary_m,
                              observation.speed_m_s)) or observation.speed_m_s < 0 or
                (self.last_time_s is not None and observation.time_s <= self.last_time_s)):
            raise ValueError("invalid or unordered original observation")
        if observation.signal not in {"steady_red_alone", "other", "unknown"}:
            raise ValueError("unrecognized signal observation")
        if any(type(value) is not bool for value in
               (observation.pedestrian_conflict, observation.traffic_conflict,
                observation.junction_exited)):
            raise ValueError("conflict and exit observations must be booleans")
        self.last_time_s = observation.time_s
        if self.phase == "approach" and observation.distance_to_stop_boundary_m <= 2:
            self.phase = "stopping" if self.stop_request == "complete_stop" else "yielding"
        if self.phase == "stopping":
            if (observation.speed_m_s <= self.stop_speed_m_s and
                    observation.distance_to_stop_boundary_m >= 0):
                if self.stop_start_s is None:
                    self.stop_start_s = observation.time_s
                if observation.time_s - self.stop_start_s >= self.stop_dwell_s:
                    self.phase = "yielding"
            else:
                self.stop_start_s = None
        if (self.phase == "yielding" and observation.signal == "steady_red_alone" and
                (self.conflict_response_request == "advance" or not (
                    observation.pedestrian_conflict or observation.traffic_conflict))):
            self.phase = "turning"
        if self.phase == "turning" and observation.junction_exited:
            self.phase = "done"
        request = {
            "approach": {"throttle": 0.25, "brake": 0.0, "steer": 0.0},
            "stopping": {"throttle": 0.0, "brake": 1.0, "steer": 0.0},
            "yielding": {"throttle": 0.0, "brake": 1.0, "steer": 0.0},
            "turning": {"throttle": 0.15, "brake": 0.0, "steer": -0.35},
            "done": {"throttle": 0.0, "brake": 1.0, "steer": 0.0},
        }[self.phase]
        row = {"time_s": observation.time_s, "phase": self.phase,
               "signal": observation.signal,
               "pedestrian_conflict": observation.pedestrian_conflict,
               "traffic_conflict": observation.traffic_conflict,
               "stop_request": self.stop_request,
               "conflict_response_request": self.conflict_response_request,
               "stop_start_s": self.stop_start_s, "control_request": request.copy(),
               "engineering_only": True}
        self.history.append(row)
        return row


def controller_for_case(suffix: str) -> RedLeftTurnController:
    """Map one exact draft attempt to requests without asserting realization."""
    from build_case_plan import KINDS

    if suffix not in KINDS:
        raise ValueError("unknown exact C153046 case")
    stop, _, _, conflict = KINDS[suffix]
    response = "advance" if conflict.endswith("advance") else "yield"
    return RedLeftTurnController(stop_request=stop, conflict_response_request=response)
