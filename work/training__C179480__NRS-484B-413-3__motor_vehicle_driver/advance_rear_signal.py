"""CPU construction for the two NRS 484B.413(3) timing targets.

This schedules controls and describes observations to retain. It does not
decide whether an observed signal was legally appropriate or a decrease sudden.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TimingPlan:
    rate_hz: int = 20
    action_frame: int = 120
    signal_lead_frames: int = 20
    rear_gap_m: float = 12.0
    sudden_deceleration_mps2: float = 3.0

    def __post_init__(self):
        if self.rate_hz <= 0 or self.action_frame <= 1:
            raise ValueError("Invalid frame clock or action frame")
        if not 0 < self.signal_lead_frames < self.action_frame:
            raise ValueError("Signal lead must precede the action")
        if self.rear_gap_m <= 0 or self.sudden_deceleration_mps2 <= 0:
            raise ValueError("Declared gap and deceleration bounds must be positive")


def target(case_suffix: str, plan: TimingPlan = TimingPlan()) -> dict:
    """Return fixed clock/context with the one declared signal-time difference."""
    if case_suffix not in ("witness_1", "witness_2"):
        raise ValueError("Unknown selected case")
    signal_frame = (plan.action_frame - plan.signal_lead_frames
                    if case_suffix == "witness_1" else plan.action_frame + 40)
    return {
        "case_suffix": case_suffix,
        "rate_hz": plan.rate_hz,
        "action_frame": plan.action_frame,
        "brake_lamp_command_frame": signal_frame,
        "signal_lead_frames": plan.signal_lead_frames,
        "rear_gap_m": plan.rear_gap_m,
        "sudden_deceleration_mps2": plan.sudden_deceleration_mps2,
        "rear_vehicle_same_lane_required": True,
        "required_source_rows": [
            "ego_frame_time_pose_velocity_acceleration",
            "ego_brake_lamp_and_hand_signal_state",
            "rear_vehicle_frame_time_pose_lane_and_body",
            "road_lane_geometry_and_surface_gap",
        ],
        "diagnostic_only": True,
    }
