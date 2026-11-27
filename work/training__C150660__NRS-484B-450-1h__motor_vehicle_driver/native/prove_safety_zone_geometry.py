"""Positive and negative 600-frame diagnostic geometry proof."""

from safety_zone_geometry import FRAME_COUNT, FRAME_RATE, THIRTY_FEET_M, audit_selected_pair, measure_frame, measure_trace


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


zone = {
    "x_start_m": 0.0, "x_end_m": 20.0, "curb_y_m": 0.0, "zone_near_y_m": 3.0,
    "zone_map_source": "synthetic diagnostic map", "curb_map_source": "synthetic diagnostic curb",
}
inside = [(8.0, 0.4), (10.0, 0.4), (10.0, 2.0), (8.0, 2.0)]
outside = [(40.0, 0.4), (42.0, 0.4), (42.0, 2.0), (40.0, 2.0)]
assert measure_frame(inside, zone)["fully_between_zone_and_curb"]
assert not measure_frame(outside, zone)["fully_between_zone_and_curb"]
assert not measure_frame(outside, zone)["within_30_feet_of_opposite_end_points"]
assert THIRTY_FEET_M == 9.144
for offset, expected in ((THIRTY_FEET_M - .001, True),
                         (THIRTY_FEET_M, True),
                         (THIRTY_FEET_M + .001, False)):
    footprint = [(20 + offset, 0), (22 + offset, 0),
                 (20 + offset, 1), (22 + offset, 1)]
    assert measure_frame(footprint, zone)["within_30_feet_of_opposite_end_points"] is expected
    # CARLA's x-major four-corner order must not create a crossing polygon.
    assert measure_frame([footprint[i] for i in (0, 2, 1, 3)], zone)[
        "within_30_feet_of_opposite_end_points"] is expected
    start_footprint = [(-offset - 2, 0), (-offset, 0),
                       (-offset - 2, 1), (-offset, 1)]
    assert measure_frame(start_footprint, zone)["within_30_feet_of_opposite_end_points"] is expected
rows = [{
    "frame": i, "time_s": i / FRAME_RATE,
    "vehicle_stopped": 100 <= i < 500,
    "stop_state_source": "synthetic_native_sample",
    "vehicle_footprint_corners_m": inside if i < 500 else outside,
} for i in range(FRAME_COUNT)]
m = measure_trace(rows, zone)
assert m["stopped_between_frames"] == 400
assert m["legal_conclusion"] is None
between_rows = [dict(row, vehicle_footprint_corners_m=inside) for row in rows]
outside_rows = [dict(row, vehicle_footprint_corners_m=outside) for row in rows]
pair = audit_selected_pair(between_rows, outside_rows, zone)
assert pair["between"]["stopped_between_frames"] == 400
assert pair["outside"]["stopped_between_frames"] == 0
assert pair["isolation_checked"] and not pair["physical_zone_confirmed"]
bad_pair = [dict(row) for row in outside_rows]
bad_pair[100]["vehicle_stopped"] = False
reject(lambda: audit_selected_pair(between_rows, bad_pair, zone), "changed fixed")
bad_pair = [dict(row) for row in outside_rows]
bad_pair[100]["stop_state_source"] = "other_source"
reject(lambda: audit_selected_pair(between_rows, bad_pair, zone), "changed fixed")
reject(lambda: audit_selected_pair(between_rows, between_rows, zone), "lacks isolated")
reject(lambda: measure_trace(rows[:-1], zone), "600 frames")
bad = [dict(row) for row in rows]
bad[100]["time_s"] = 99.0
reject(lambda: measure_trace(bad, zone), "20 Hz join")
bad = [dict(row) for row in rows]
bad[100]["stop_state_source"] = ""
reject(lambda: measure_trace(bad, zone), "stop-state source")
bad_zone = dict(zone, zone_map_source="")
reject(lambda: measure_trace(rows, bad_zone), "source provenance")
reject(lambda: measure_frame([(0, 0)] * 4, zone), "degenerate")
print("PASS: 600-frame safety-zone footprint, both curb endpoints, 30-foot below/at/above and negative CPU proof")
