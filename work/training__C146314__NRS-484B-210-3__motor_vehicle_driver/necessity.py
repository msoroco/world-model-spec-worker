"""Explicit lateral-clearance test for whether a right pass fits on pavement."""
from geometry import (PAVED_RIGHT_EDGE_Y_M, LEAD_LEFT_LANE_Y_M, LEAD_RIGHT_LANE_Y_M,
                      EGO_PAVED_PASS_Y_M, EGO_SHOULDER_PASS_Y_M)

BODY_WIDTH_M = 1.8
SIDE_CLEARANCE_M = 0.4


def paved_right_pass_feasible(lead_y_m, ego_width_m=BODY_WIDTH_M,
                              lead_width_m=BODY_WIDTH_M,
                              clearance_m=SIDE_CLEARANCE_M):
    """The entire ego body must fit between lead's right edge and paved edge."""
    if min(ego_width_m, lead_width_m) <= 0 or clearance_m < 0:
        raise ValueError('Invalid vehicle or clearance dimensions')
    available = (lead_y_m - lead_width_m / 2) - PAVED_RIGHT_EDGE_Y_M
    needed = ego_width_m + clearance_m
    return {'available_right_paved_m': round(available, 5),
            'needed_m': round(needed, 5),
            'feasible': available >= needed}


def check():
    paved = paved_right_pass_feasible(LEAD_LEFT_LANE_Y_M)
    shoulder = paved_right_pass_feasible(LEAD_RIGHT_LANE_Y_M)
    if not paved['feasible'] or shoulder['feasible']:
        raise ValueError('Comparison no longer separates paved right-pass clearance')
    if EGO_PAVED_PASS_Y_M + BODY_WIDTH_M / 2 > LEAD_LEFT_LANE_Y_M - BODY_WIDTH_M / 2 - SIDE_CLEARANCE_M:
        raise ValueError('Paved ego route lacks lead clearance')
    if EGO_PAVED_PASS_Y_M - BODY_WIDTH_M / 2 < PAVED_RIGHT_EDGE_Y_M:
        raise ValueError('Paved ego route leaves pavement')
    if EGO_SHOULDER_PASS_Y_M + BODY_WIDTH_M / 2 > LEAD_RIGHT_LANE_Y_M - BODY_WIDTH_M / 2 - SIDE_CLEARANCE_M:
        raise ValueError('Shoulder ego route lacks lead clearance')
    if EGO_SHOULDER_PASS_Y_M - BODY_WIDTH_M / 2 >= PAVED_RIGHT_EDGE_Y_M:
        raise ValueError('Shoulder ego route fails to leave pavement')
    return {'paved_case': paved, 'shoulder_case': shoulder,
            'necessity_is_geometry_plan_only': True, 'native_body_dimensions_pending': True}
