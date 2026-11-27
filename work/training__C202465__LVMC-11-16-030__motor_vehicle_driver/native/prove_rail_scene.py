"""Exercise exact-case 600-frame rail geometry and exception readbacks."""

import json
from pathlib import Path

from rail_scene import ray_clear, sight_row
from rail_sight import FRAME_COUNT, measure_trace, speed_request


def reject(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


railway = {"source_ref": "native:surveyed-rail", "crossing_xy_m": [0, 0],
           "unit_direction_xy": [0, 1], "grade_crossing": True}
blockers = [{"source_ref": "native:opaque-building", "opaque": True,
             "edge_xy_m": [[-2, -125], [-2, -.3]]}]
right_blockers = [{"source_ref": "native:right-opaque-building", "opaque": True,
                   "edge_xy_m": [[-2, .3], [-2, 125]]}]
crossing_blockers = [{"source_ref": "native:crossing-opaque-building", "opaque": True,
                      "edge_xy_m": [[-2, -.3], [-2, .3]]}]
SIGHT_BLOCKERS = {"left_sight_obscured": blockers,
                  "right_sight_obscured": right_blockers,
                  "crossing_obscured": crossing_blockers,
                  "clear_both": []}
flagman = {"source_ref": "native:flagman-readback", "on_duty": False}
signal = {"source_ref": "native:signal-readback", "installed": False,
          "visible": False, "indicates_approach": False}
crossing = {"grade_crossing_source": railway["source_ref"],
            "railway_source": railway["source_ref"],
            "approach_route_source": "native:ego-route"}


def make_rows(speed_mode, barrier=blockers, duty=False, inactive=False,
              active=False, installed_not_visible=False):
    rows = []
    for frame in range(FRAME_COUNT):
        distance = 50 - .12 * frame
        ego = {"source_ref": "native:ego-body", "observer_xy_m": [-distance, 0],
               "distance_to_crossing_m": distance,
               "speed_mps": speed_request(speed_mode),
               "traversing_grade_crossing": -5 <= distance <= 0}
        rail_traffic = [
            {"source_ref": "native:left-rail-vehicle", "kind": "rail_vehicle",
             "side": "left", "center_xy_m": [0, -70 + .01*frame]},
            {"source_ref": "native:right-rail-vehicle", "kind": "rail_vehicle",
             "side": "right", "center_xy_m": [0, 70 - .01*frame]},
        ]
        row = sight_row(frame, ego, railway, rail_traffic, barrier,
                        dict(flagman, on_duty=duty),
                        dict(signal, installed=inactive or active or installed_not_visible,
                             visible=inactive or active, indicates_approach=active))
        rows.append(row)
    return rows


assert not ray_clear((-50, 0), (0, -100), blockers)
assert ray_clear((-50, 0), (0, 100), blockers)
assert ray_clear((-50, 0), (0, 0), blockers)
slow = make_rows("slower_traversal")
fast = make_rows("faster_traversal")
slow_measure = measure_trace(slow, crossing)
fast_measure = measure_trace(fast, crossing)
assert slow_measure["last_100_feet_missing_view_frames"] > 0
assert slow_measure["maximum_traversal_speed_mps"] < slow_measure["fifteen_mph_mps"]
assert fast_measure["maximum_traversal_speed_mps"] > fast_measure["fifteen_mph_mps"]
assert slow_measure["flagman_on_duty_frames"] == 0
assert measure_trace(make_rows("slower_traversal", duty=True), crossing)["flagman_on_duty_frames"] == FRAME_COUNT
assert measure_trace(make_rows("slower_traversal", inactive=True), crossing)["visible_inactive_signal_frames"] == FRAME_COUNT
assert measure_trace(make_rows("slower_traversal", barrier=[]), crossing)["last_100_feet_missing_view_frames"] == 0
plan = json.loads((Path(__file__).resolve().parents[1] / "case-plan.json").read_text())
assert len(plan["cases"]) == 9 and len(plan["comparisons"]) == 8
for case in plan["cases"]:
    design = case["construction_design"]
    state = design["exception_state"]
    rows = make_rows(design["speed_mode"], SIGHT_BLOCKERS[design["sight_mode"]],
                     duty=state == "flagman_on_duty",
                     inactive=state == "visible_inactive_signal",
                     active=state == "visible_active_signal",
                     installed_not_visible=state == "installed_not_visible")
    measurement = measure_trace(rows, crossing)
    assert bool(measurement["last_100_feet_missing_view_frames"]) == (design["sight_mode"] != "clear_both")
    assert bool(measurement["flagman_on_duty_frames"]) == (state == "flagman_on_duty")
    assert bool(measurement["visible_inactive_signal_frames"]) == (state == "visible_inactive_signal")
    assert measurement["legal_visibility_conclusion"] is None

ego0 = {"source_ref": "native:ego-body", "observer_xy_m": [-50, 0],
        "distance_to_crossing_m": 50, "speed_mps": 6,
        "traversing_grade_crossing": False}
traffic0 = [{"source_ref": "native:left", "kind": "rail_vehicle", "side": "left", "center_xy_m": [0, -70]},
            {"source_ref": "native:right", "kind": "rail_vehicle", "side": "right", "center_xy_m": [0, 70]}]
reject(lambda: sight_row(0, ego0, railway, traffic0[:1], blockers, flagman, signal), "both directions")
reject(lambda: sight_row(0, ego0, railway, traffic0, blockers, {}, signal), "flagman duty")
reject(lambda: sight_row(0, ego0, railway, traffic0, blockers, flagman, {}), "signal readback")
reject(lambda: sight_row(0, ego0, railway, traffic0,
                         [dict(blockers[0], source_ref="")], flagman, signal), "original source")
reject(lambda: sight_row(0, ego0, dict(railway, grade_crossing=False), traffic0,
                         blockers, flagman, signal), "grade crossing")
print("PASS: dynamic 600-frame two-direction rail geometry, speed and exception-source proof")
