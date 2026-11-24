"""CPU proposal to narrow entry/turn sampling brackets near 200 feet.

This is an engineering control request, not measured Native speed or a
substitute for source-body event brackets in measure_center_lane.py.
"""
import math

HZ = 20
NORMAL_SPEED_MPS = 5.0
EVENT_SPEED_MPS = 2.4
POSITION_ERROR_M = 0.02
WINDOW_M = 4.0
THRESHOLD_M = 200 * 0.3048


def target_speed(station_m, entry_station_m, turn_station_m):
    values = (station_m, entry_station_m, turn_station_m)
    if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
        raise ValueError('Finite source route stations required')
    if entry_station_m < 0 or turn_station_m <= entry_station_m:
        raise ValueError('Entry and turn station ordering differs')
    near_event = (abs(station_m - entry_station_m) <= WINDOW_M
                  or abs(station_m - turn_station_m) <= WINDOW_M)
    return EVENT_SPEED_MPS if near_event else NORMAL_SPEED_MPS


def bracket_budget(event_speed_mps=EVENT_SPEED_MPS,
                   position_error_m=POSITION_ERROR_M):
    if not (math.isfinite(event_speed_mps) and 0 < event_speed_mps <= NORMAL_SPEED_MPS
            and math.isfinite(position_error_m) and position_error_m >= 0):
        raise ValueError('Finite positive event speed and position uncertainty required')
    # Entry and turn are independently bracketed by one 20-Hz interval each.
    # Endpoint coordinate error can affect both event segments.
    width = 2 * event_speed_mps / HZ + 2 * position_error_m
    return {'event_speed_mps': event_speed_mps,
            'position_error_m': position_error_m,
            'maximum_two_event_interval_width_m': width,
            'one_foot_probe_spacing_m': 0.3048,
            'one_foot_spacing_exceeds_budget': width < 0.3048}


def relation(true_distance_m, budget_m):
    if not (math.isfinite(true_distance_m) and math.isfinite(budget_m)
            and true_distance_m >= 0 and budget_m >= 0):
        raise ValueError('Finite nonnegative distance and budget required')
    lower = true_distance_m - budget_m / 2
    upper = true_distance_m + budget_m / 2
    return 'within' if upper <= THRESHOLD_M else 'exceeds' if lower > THRESHOLD_M else 'unresolved'
