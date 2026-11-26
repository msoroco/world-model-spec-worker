"""Pure requested motion for roundabout lane and pass-duration probes.

Requests are engineering controls. Original Native lane, speed and passing
observations must be measured independently from the executed actor state.
"""

from dataclasses import dataclass


OUTER_RIGHT_RADIUS_M = 14.5
INNER_LEFT_RADIUS_M = 11.5


@dataclass(frozen=True)
class SourceState:
    ego_speed_mps: float
    ego_radius_m: float
    follower_gap_arc_m: float
    slow_vehicle_ahead_arc_m: float | None
    slow_vehicle_speed_mps: float | None
    slow_vehicle_cleared: bool
    right_lane_center_radius_m: float = OUTER_RIGHT_RADIUS_M
    left_lane_center_radius_m: float = INNER_LEFT_RADIUS_M


@dataclass(frozen=True)
class Request:
    target_radius_m: float
    target_speed_mps: float
    phase: str
    pass_requested: bool


def request(case_suffix: str, state: SourceState) -> Request:
    """Compute a target from source state without asserting a legal outcome."""
    if state.ego_speed_mps < 0 or state.follower_gap_arc_m < 0:
        raise ValueError('Original ego or follower motion source invalid')
    if not 0 < state.left_lane_center_radius_m < state.right_lane_center_radius_m:
        raise ValueError('Original surveyed lane radii invalid')
    if case_suffix == 'probe_a':
        return Request(state.right_lane_center_radius_m, 3.0, 'right_lane_slow', False)
    if case_suffix == 'probe_b':
        return Request(state.left_lane_center_radius_m, 3.0, 'left_lane_slow', False)
    if case_suffix not in ('necessary_pass', 'post_pass_linger'):
        raise ValueError('Unknown exact roundabout case')
    if state.slow_vehicle_ahead_arc_m is None or state.slow_vehicle_speed_mps is None:
        raise ValueError('Pass case requires original slower-vehicle source')
    if state.slow_vehicle_speed_mps < 0:
        raise ValueError('Original slower-vehicle speed invalid')
    if not state.slow_vehicle_cleared:
        return Request(state.left_lane_center_radius_m, 4.0, 'pass_in_progress', True)
    if case_suffix == 'necessary_pass':
        return Request(state.right_lane_center_radius_m, 3.0, 'return_after_pass', False)
    return Request(state.left_lane_center_radius_m, 3.0, 'linger_after_pass', False)
