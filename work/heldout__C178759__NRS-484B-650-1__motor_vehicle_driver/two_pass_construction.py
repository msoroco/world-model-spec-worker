"""Physical request plan for two distinct right passes of one fixed vehicle.

This is an engineering controller plan, not evidence that a pass or violation
occurred. A Native runner must retain body/road geometry and check transitions.
"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Phase:
    name: str
    start_m: float
    end_m: float
    ego_target: str
    ego_speed_mps: float
    lead_speed_mps: float


PHASES = (
    Phase('approach', 0, 260, 'paved_lane', 16, 16),
    Phase('first_right_pass_request', 260, 450, 'right_of_paved_edge', 24, 10),
    Phase('first_reentry', 450, 500, 'paved_lane', 12, 12),
    Phase('lead_reclaim_request', 500, 580, 'right_of_paved_edge', 6, 20),
    Phase('second_reentry', 580, 660, 'paved_lane', 12, 12),
    Phase('second_right_pass_request', 660, 880, 'right_of_paved_edge', 24, 10),
    Phase('exit', 880, 2200, 'paved_lane', 16, 16),
)


def validate_schedule(phases=PHASES):
    if len(phases) != 7 or phases[0].start_m != 0:
        raise ValueError('Two-pass phase inventory differs')
    if any(a.end_m != b.start_m for a, b in zip(phases, phases[1:])):
        raise ValueError('Two-pass route station schedule has a gap or overlap')
    labels = [p.name for p in phases]
    if labels.index('first_right_pass_request') >= labels.index('first_reentry') or labels.index('second_reentry') >= labels.index('second_right_pass_request'):
        raise ValueError('Two-pass reentry does not separate pass requests')
    for phase in phases:
        if phase.start_m >= phase.end_m or phase.ego_target not in ('paved_lane', 'right_of_paved_edge'):
            raise ValueError('Invalid two-pass target')
        if not all(isfinite(v) and 0 <= v <= 30 for v in (phase.ego_speed_mps, phase.lead_speed_mps)):
            raise ValueError('Invalid controller speed request')
    return True


def phase_at(ego_station_m):
    validate_schedule()
    if not isfinite(ego_station_m):
        raise ValueError('Missing finite ego route station')
    for phase in PHASES:
        if phase.start_m <= ego_station_m < phase.end_m:
            return phase
    raise ValueError('Ego route station outside two-pass request plan')


def transition_guard(previous, current, ego_minus_lead_m, ego_right_of_mapped_edge_m):
    """Fail closed when original geometry contradicts an intended phase.

    `ego_minus_lead_m` is signed route progress: negative means lead ahead.
    Edge clearance is measured from retained Native road geometry, not inferred
    from a requested lateral target. Actual pavement material remains pixel review.
    """
    if previous == current:
        return True
    if current not in {p.name for p in PHASES}:
        raise ValueError('Unknown physical phase')
    if not all(isfinite(v) for v in (ego_minus_lead_m, ego_right_of_mapped_edge_m)):
        raise ValueError('Missing original vehicle or mapped-edge geometry')
    if current == 'first_right_pass_request' and ego_minus_lead_m >= -5:
        raise ValueError('Fixed vehicle is not ahead before first pass')
    if current == 'first_reentry' and ego_minus_lead_m <= 5:
        raise ValueError('First order reversal was not realized')
    if current == 'lead_reclaim_request' and ego_right_of_mapped_edge_m > 0:
        raise ValueError('First mapped-edge reentry was not realized')
    if current == 'second_reentry' and ego_minus_lead_m >= -5:
        raise ValueError('Fixed vehicle did not reclaim the lead')
    if current == 'second_right_pass_request' and (ego_minus_lead_m >= -5 or ego_right_of_mapped_edge_m > 0):
        raise ValueError('Second pass lacks reset and mapped-edge reentry')
    return True
