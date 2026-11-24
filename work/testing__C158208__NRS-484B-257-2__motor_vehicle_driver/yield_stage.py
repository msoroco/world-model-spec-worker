"""Exact C158208 signed-entrance construction knobs for Native staging.

These are engineering targets and spawn points, never legal hazard thresholds.
Observed bodies and speed from yield_capture.py determine what happened.
"""

from dataclasses import dataclass
import math

PREFIX = "testing__C158208__NRS-484B-257-2__motor_vehicle_driver__"
KINDS = ("yield_other_inside", "yield_other_approaching", "yield_other_obligated",
         "yield_no_slow", "officer_control_exception")


@dataclass(frozen=True)
class Stage:
    case_id: str
    other_release_tick: int = 0
    approach_speed_mps: float = 8.0
    reference_speed_mps: float = 2.0

    def __post_init__(self):
        if self.case_id not in {PREFIX + kind for kind in KINDS}:
            raise ValueError("Unknown exact signed-entrance case")
        if type(self.other_release_tick) is not int or self.other_release_tick < 0:
            raise ValueError("Invalid other-vehicle release tick")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
               for v in (self.approach_speed_mps, self.reference_speed_mps)):
            raise ValueError("Invalid engineering speed target")
        if self.kind != "yield_no_slow" and self.reference_speed_mps >= self.approach_speed_mps:
            raise ValueError("Yield-response construction needs lower reference target")

    @property
    def kind(self):
        return self.case_id.removeprefix(PREFIX)

    @property
    def other_stop_sign(self):
        return self.kind == "yield_other_obligated"

    @property
    def officer_control_source_required(self):
        return self.kind == "officer_control_exception"

    @property
    def other_start_xy_m(self):
        # CARLA coordinates: south approach advances from positive Y toward 0.
        return (1.8, -4.0) if self.kind != "yield_other_approaching" else (1.8, 25.0)

    def target_ego_speed(self, *, before_reference, other_body_clear):
        if type(before_reference) is not bool or type(other_body_clear) is not bool:
            raise ValueError("Missing observed reference/other-body state")
        if self.kind == "yield_no_slow":
            return self.approach_speed_mps
        if before_reference and not other_body_clear:
            return self.reference_speed_mps
        return self.approach_speed_mps

    def target_other_speed(self, tick):
        if type(tick) is not int or tick < 0:
            raise ValueError("Missing Native tick index")
        return 0.0 if tick < self.other_release_tick else 5.0


def primary(case_id):
    kind = case_id.removeprefix(PREFIX)
    return Stage(case_id, other_release_tick=80 if kind == "yield_other_approaching" else 150)
