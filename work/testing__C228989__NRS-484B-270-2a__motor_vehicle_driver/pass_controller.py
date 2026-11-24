"""Fail-closed physical control intent for the NRS 484B.270(2)(a) scenes.

This produces commands for a Native adapter. It never decides legal due care,
lane availability, or reasonable safety, which require source review.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Observation:
    ego_lane: str
    control_lane: str
    immediate_left_lane: str | None
    same_direction_lane_count: int
    longitudinal_gap_m: float
    relative_speed_mps: float
    left_lane_occupants: tuple[str, ...]
    left_lane_restricted: bool
    left_lane_obstructed: bool
    source_frame: int


def command(request: str, sample: Observation) -> dict:
    """Return an adapter-neutral command with an auditable physical reason.

    A request to move left is inhibited when sampled constraints are adverse.
    The adapter must re-evaluate this function each 20 Hz frame; the command
    does not grant a sustained lane-change authorization.
    """
    if request not in {"move_left", "stay", "pass", "follow"}:
        raise ValueError("unknown exact maneuver request")
    if not isinstance(sample.source_frame, int) or sample.source_frame < 0:
        raise ValueError("source frame required")
    if not sample.ego_lane or not sample.control_lane or sample.ego_lane != sample.control_lane:
        raise ValueError("same initial actor lane source required")
    if sample.same_direction_lane_count not in {1, 2}:
        raise ValueError("unsupported source lane count")
    if not all(math.isfinite(x) for x in (sample.longitudinal_gap_m, sample.relative_speed_mps)):
        raise ValueError("finite relative motion required")
    if sample.longitudinal_gap_m <= 0:
        raise ValueError("control must be ahead")
    if not isinstance(sample.left_lane_occupants, tuple) or any(not isinstance(x, str) or not x for x in sample.left_lane_occupants):
        raise ValueError("source left-lane occupancy required")
    if sample.same_direction_lane_count == 1 and sample.immediate_left_lane is not None:
        raise ValueError("single-lane scene cannot claim immediate-left lane")
    if sample.same_direction_lane_count == 2 and (not sample.immediate_left_lane or sample.immediate_left_lane == sample.ego_lane):
        raise ValueError("source immediate-left lane required")
    if request in {"move_left", "stay"} and sample.same_direction_lane_count != 2:
        raise ValueError("two-lane request in one-lane scene")
    if request in {"pass", "follow"} and sample.same_direction_lane_count != 1:
        raise ValueError("one-lane request in two-lane scene")
    if request == "move_left":
        adverse = (sample.left_lane_occupants or sample.left_lane_restricted or
                   sample.left_lane_obstructed)
        if adverse:
            return {"source_frame": sample.source_frame, "lane_change": "none",
                    "longitudinal": "hold_back", "reason": "sampled_left_lane_constraint"}
        return {"source_frame": sample.source_frame, "lane_change": "immediate_left",
                "longitudinal": "hold_back", "reason": "physical_move_request"}
    if request == "follow":
        return {"source_frame": sample.source_frame, "lane_change": "none",
                "longitudinal": "follow_control", "reason": "one_lane_follow_request"}
    if request == "pass":
        return {"source_frame": sample.source_frame, "lane_change": "none",
                "longitudinal": "pass_control", "reason": "one_lane_pass_request"}
    return {"source_frame": sample.source_frame, "lane_change": "none",
            "longitudinal": "pass_control", "reason": "two_lane_stay_request"}


def command_for_case(case: dict, sample: Observation) -> dict:
    """Bind one planned exact case to sampled Native lane/traffic state."""
    if case.get("target_law_id") != "NRS-484B-270-2a" or case.get("cell_id") != "C228989":
        raise ValueError("wrong exact law or cell")
    if case.get("actor") != "motor_vehicle_driver" or case.get("control_kind") not in {
            "bicycle", "electric_bicycle", "electric_scooter"}:
        raise ValueError("wrong actor or nonqualifying control")
    if case.get("same_direction_lane_count_requested") != sample.same_direction_lane_count:
        raise ValueError("actual lane count differs from planned case")
    requested_traffic = case.get("left_lane_traffic_requested")
    if requested_traffic == "open" and sample.left_lane_occupants:
        raise ValueError("open-lane case has source-recorded occupant")
    if requested_traffic == "occupied" and not sample.left_lane_occupants:
        raise ValueError("occupied-lane case lacks source-recorded occupant")
    if requested_traffic not in {"open", "occupied", "not_applicable"}:
        raise ValueError("unknown traffic request")
    return command(case.get("ego_maneuver_request"), sample)
