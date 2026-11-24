"""Positive and negative 600-frame diagnostic geometry proof."""

from safety_zone_geometry import FRAME_COUNT, FRAME_RATE, THIRTY_FEET_M, measure_frame, measure_trace


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
rows = [{
    "frame": i, "time_s": i / FRAME_RATE,
    "vehicle_stopped": 100 <= i < 500,
    "stop_state_source": "synthetic_native_sample",
    "vehicle_footprint_corners_m": inside if i < 500 else outside,
} for i in range(FRAME_COUNT)]
m = measure_trace(rows, zone)
assert m["stopped_between_frames"] == 400
assert m["legal_conclusion"] is None
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
print("PASS: 600-frame safety-zone footprint and 30-foot geometry positive/negative CPU proof")
