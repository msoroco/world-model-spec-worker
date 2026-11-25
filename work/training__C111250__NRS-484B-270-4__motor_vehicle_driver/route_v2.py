"""Engineering routes for the two C111250 bicycle-facility cases.

These are requested center paths. Saved Native body corners, not a center-path
flag, determine the measured occupancy. No statutory cutoff is encoded here.
"""
from math import isfinite

from facility import CYCLE_LANE, INTERSECTION, body_overlap


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def route_x(case_suffix, y_m):
    if not isfinite(y_m):
        raise ValueError("Nonfinite route station")
    if case_suffix == "outside_cycle_lane":
        # A brief crossing of the facility inside the junction, then return
        # to the motor lane. The exception circumstance needs original proof.
        lateral = smoothstep((y_m + 7.0) / 2.0) * (1.0 - smoothstep((y_m + 1.0) / 2.0))
        return 1.75 + 2.7 * lateral
    if case_suffix == "within_cycle_lane":
        return 4.45
    raise ValueError("Unknown exact cycle-facility case")


def body_at(case_suffix, y_m, speed_mps=4.0):
    x_m = route_x(case_suffix, y_m)
    return {"body_xy_m": [[x_m - .9, y_m - 1.0],
                          [x_m + .9, y_m - 1.0],
                          [x_m + .9, y_m + 1.0],
                          [x_m - .9, y_m + 1.0]],
            "speed_mps": speed_mps}


def check():
    stations = [round(-12 + index * .1, 3) for index in range(241)]
    crossing = [body_overlap(body_at("outside_cycle_lane", y)) for y in stations]
    sustained = [body_overlap(body_at("within_cycle_lane", y)) for y in stations]
    crossing_frames = sum(row["cycle_intersection_body_overlap_m2"] > 0 for row in crossing)
    sustained_frames = sum(row["cycle_intersection_body_overlap_m2"] > 0 for row in sustained)
    if not 0 < crossing_frames < sustained_frames:
        raise ValueError("Requested crossing and sustained occupancy are not separated")
    for y_m in (-12.0, -8.0, 8.0, 12.0):
        if route_x("outside_cycle_lane", y_m) != 1.75:
            raise ValueError("Crossing route did not return to the motor lane")
    if not CYCLE_LANE == (3.5, 5.5) or not INTERSECTION == (-7.0, 7.0):
        raise ValueError("Facility geometry changed")
    return {"passed": True, "route_station_count": len(stations),
            "crossing_overlap_stations": crossing_frames,
            "sustained_overlap_stations": sustained_frames,
            "source_kind": "authored_engineering_route_only",
            "native_executed": False, "legal_exception_proven": False}
