"""Portable geometry for a roadway stop and an unobstructed contrast.

The caller supplies surveyed lane and shoulder widths. This plans physical
targets; whether traffic was actually impeded must be measured after capture.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RoadProfile:
    lane_width_m: float
    shoulder_width_m: float
    vehicle_width_m: float
    clearance_m: float = 0.25

    def validate(self):
        if min(self.lane_width_m, self.shoulder_width_m,
               self.vehicle_width_m, self.clearance_m) <= 0:
            raise ValueError('Road widths and clearance must be positive')
        if self.vehicle_width_m + 2 * self.clearance_m >= self.lane_width_m:
            raise ValueError('Vehicle and clearance do not fit the surveyed lane')
        if self.vehicle_width_m + 2 * self.clearance_m > self.shoulder_width_m:
            raise ValueError('Contrast vehicle cannot clear the surveyed lane')


def target(profile: RoadProfile, blocks: bool):
    """Return lateral stop target and a through-traffic route in lane coordinates.

    Lane center is y=0; positive y is the surveyed right shoulder. The same
    approaching actor follows lane center in both cases.
    """
    profile.validate()
    if type(blocks) is not bool:
        raise ValueError('blocks must be an exact Boolean')
    lateral_m = 0.0 if blocks else (
        profile.lane_width_m + profile.shoulder_width_m) / 2
    ego_min = lateral_m - profile.vehicle_width_m / 2
    ego_max = lateral_m + profile.vehicle_width_m / 2
    lane_edge = profile.lane_width_m / 2
    if blocks and not (ego_min < lane_edge and ego_max > -lane_edge):
        raise AssertionError('Reference stop missed the travel lane')
    if not blocks and ego_min - profile.clearance_m < lane_edge:
        raise AssertionError('Contrast stop still intrudes into the travel lane')
    return {
        'ego_stop_lateral_m': lateral_m,
        'approaching_actor_lateral_m': 0.0,
        'approaching_actor_route': 'same surveyed travel lane',
        'planned_lane_overlap': blocks,
        'safe_operation_necessity': 'measure_from_original_sources',
        'compliance_with_law': 'measure_from_original_sources',
        'actual_impediment': 'measure_from_original_sources',
    }
