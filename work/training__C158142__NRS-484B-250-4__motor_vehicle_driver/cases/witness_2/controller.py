"""Pre-capture control policy for the selected inoperative-signal branch.

Inputs are Native observations, never legal labels. The policy requires an
installed, uncovered, inoperative signal on the ego lane. Native execution
must still establish those facts from the actual scene and source pixels.
"""
from dataclasses import dataclass


RATE_HZ = 20
STOP_FRAMES = 20  # engineering dwell for an observable complete stop
HALT_SPEED_MPS = 0.05  # sensor tolerance, not a statutory threshold


@dataclass(frozen=True)
class Observation:
    frame: int
    signal_installed: bool
    signal_uncovered: bool
    signal_inoperative: bool
    signal_governs_ego_lane: bool
    stop_line_present: bool
    near_crosswalk_present: bool
    ego_front_distance_to_boundary_m: float
    ego_speed_mps: float
    prior_stop_vehicle_approaching: bool
    vehicle_in_intersection: bool


@dataclass(frozen=True)
class Command:
    throttle: float
    brake: float
    phase: str


class InoperativeSignalController:
    def __init__(self, expected_stop_line_present=False):
        self.expected_stop_line_present = expected_stop_line_present
        self.phase = "approach"
        self.stopped_frames = 0
        self.last_frame = -1

    def step(self, observation: Observation) -> Command:
        o = observation
        if o.frame != self.last_frame + 1:
            raise ValueError("nonconsecutive Native observation")
        self.last_frame = o.frame
        if not (o.signal_installed and o.signal_uncovered and
                o.signal_inoperative and o.signal_governs_ego_lane):
            raise ValueError("inoperative signal activation source missing")
        if o.stop_line_present != self.expected_stop_line_present:
            raise ValueError("stop-line hierarchy changed")
        if not o.stop_line_present and not o.near_crosswalk_present:
            raise ValueError("selected crosswalk boundary missing")
        if self.phase in ("approach", "hold", "yield"):
            if o.ego_front_distance_to_boundary_m <= 0:
                raise ValueError("ego crossed boundary before release")
            if self.phase == "approach":
                self.phase = "hold" if (o.ego_front_distance_to_boundary_m <= 5.0
                                        and o.ego_speed_mps <= HALT_SPEED_MPS) else "approach"
            if self.phase == "hold":
                if o.ego_speed_mps > HALT_SPEED_MPS:
                    self.stopped_frames = 0
                    self.phase = "approach"
                else:
                    self.stopped_frames += 1
                    if self.stopped_frames >= STOP_FRAMES:
                        self.phase = "yield"
            if self.phase == "yield" and not (o.prior_stop_vehicle_approaching or
                                             o.vehicle_in_intersection):
                self.phase = "released"
        if self.phase == "released":
            return Command(0.15, 0.0, self.phase)
        if self.phase == "approach" and o.ego_front_distance_to_boundary_m > 5.0:
            return Command(0.25, 0.0, self.phase)
        return Command(0.0, 1.0, self.phase)
