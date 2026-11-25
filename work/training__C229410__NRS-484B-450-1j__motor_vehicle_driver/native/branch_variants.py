"""Finite construction targets for the statutory alternatives.

Distances here are engineering targets for a sweep. They are not legal
measurements or a choice of statutory reference point.
"""
from dataclasses import dataclass

FEET_20_M = 6.096
FEET_75_M = 22.86
ENTRANCE_X = (-3.0, 3.0)


@dataclass(frozen=True)
class Branch:
    suffix: str
    side: str
    activity: str
    exception: str
    target_center_x_m: float
    spawn_center_x_m: float
    target_lane_id: int
    heading_deg: float
    context_actor: str | None = None


BRANCHES = {
    "controlled_1": Branch("controlled_1", "same", "parked", "none", 17, -40, -1, 0),
    "controlled_2": Branch("controlled_2", "same", "parked", "none", 3, -40, -1, 0),
    "same_at": Branch("same_at", "same", "parked", "none", 11.096, -40, -1, 0),
    "opposite_far": Branch("opposite_far", "opposite", "parked", "none", -35, 50, 1, 180),
    "opposite_near": Branch("opposite_near", "opposite", "parked", "none", -10, 50, 1, 180),
    "opposite_at": Branch("opposite_at", "opposite", "parked", "none", -27.86, 50, 1, 180),
    "stopped": Branch("stopped", "same", "stopped", "none", 3, -40, -1, 0),
    "standing": Branch("standing", "same", "standing", "none", 3, -40, -1, 0),
    "traffic_conflict": Branch("traffic_conflict", "same", "stopped", "traffic_conflict", 3, -40, -1, 0, "traffic_vehicle"),
    "law_direction": Branch("law_direction", "same", "stopped", "law", 3, -40, -1, 0),
    "police_direction": Branch("police_direction", "same", "stopped", "police_officer", 3, -40, -1, 0, "police_officer"),
    "device_direction": Branch("device_direction", "same", "stopped", "official_device", 3, -40, -1, 0, "official_device"),
}


def side_of_lane(lane_id):
    if lane_id == -1:
        return "south"
    if lane_id == 1:
        return "north"
    raise ValueError("Highway side requires a driving lane")


def design_gap_m(branch):
    """Center-to-entrance interval gap, before vehicle extents are measured."""
    left, right = ENTRANCE_X
    return max(0.0, left - branch.target_center_x_m,
               branch.target_center_x_m - right)


def check():
    assert FEET_20_M == 6.096 and FEET_75_M == 22.86
    assert len(BRANCHES) == len(set(BRANCHES))
    for suffix, branch in BRANCHES.items():
        assert suffix == branch.suffix
        assert branch.side == ("same" if side_of_lane(branch.target_lane_id) == "south" else "opposite")
        assert (branch.heading_deg, branch.spawn_center_x_m > branch.target_center_x_m) == ((0, False) if branch.side == "same" else (180, True))
        assert branch.activity in ("stopped", "standing", "parked")
        assert branch.exception in ("none", "traffic_conflict", "law", "police_officer", "official_device")
    assert design_gap_m(BRANCHES["controlled_1"]) > FEET_20_M
    assert design_gap_m(BRANCHES["controlled_2"]) < FEET_20_M
    assert design_gap_m(BRANCHES["opposite_far"]) > FEET_75_M
    assert design_gap_m(BRANCHES["opposite_near"]) < FEET_75_M
    return {"case_suffixes": sorted(BRANCHES), "physical_execution_claimed": False}
