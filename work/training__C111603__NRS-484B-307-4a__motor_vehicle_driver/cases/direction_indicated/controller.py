"""Source-driven requests for exact green-turn-arrow comparison cases.

These are control targets. They do not identify a governing signal, establish
another participant's lawful status, or decide whether yielding occurred.
"""

from dataclasses import dataclass


SUFFIXES = (
    'direction_indicated', 'direction_contrary',
    'arrow_lit', 'arrow_expired',
    'pedestrian_yield', 'pedestrian_overlap',
    'traffic_yield', 'traffic_overlap',
)


@dataclass(frozen=True)
class Observation:
    frame: int
    ego_before_conflict: bool
    pedestrian_in_adjacent_crosswalk: bool
    other_traffic_in_intersection: bool
    arrow_alone_illuminated: bool
    ego_speed_mps: float


@dataclass(frozen=True)
class Request:
    route: str
    target_speed_mps: float
    phase: str


def request(suffix, observed):
    if suffix not in SUFFIXES:
        raise ValueError('Unknown exact green-arrow case')
    if not 0 <= observed.frame < 600 or observed.ego_speed_mps < 0:
        raise ValueError('Original Native observation incomplete')
    route = 'contrary_turn' if suffix == 'direction_contrary' else 'indicated_turn'
    if suffix == 'arrow_expired':
        # Hold at the stop approach until the actual source light readback has
        # left the arrow interval. No request pretends to change the signal.
        if observed.arrow_alone_illuminated:
            return Request(route, 0.0, 'wait_for_observed_arrow_end')
        return Request(route, 3.0, 'after_observed_arrow_end')
    if suffix == 'arrow_lit' and not observed.arrow_alone_illuminated:
        return Request(route, 0.0, 'wait_for_observed_arrow')
    if suffix == 'pedestrian_yield' and observed.ego_before_conflict and observed.pedestrian_in_adjacent_crosswalk:
        return Request(route, 0.0, 'pause_for_observed_pedestrian')
    if suffix == 'traffic_yield' and observed.ego_before_conflict and observed.other_traffic_in_intersection:
        return Request(route, 0.0, 'pause_for_observed_traffic')
    if suffix in ('pedestrian_overlap', 'traffic_overlap'):
        return Request(route, 3.0, 'attempt_moving_overlap')
    return Request(route, 3.0, 'turn_request')
