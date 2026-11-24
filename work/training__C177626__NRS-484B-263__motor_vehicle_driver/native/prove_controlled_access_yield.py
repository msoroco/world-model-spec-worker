"""Positive and negative 600-frame controlled-access diagnostic CPU proof."""

from controlled_access_yield import FRAME_COUNT, FRAME_RATE, control_request, measure_trace


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


network = {
    "route_kind": "entry", "highway_source": "synthetic diagnostic network",
    "controlled_access_source": "synthetic diagnostic network", "ramp_lane_id": "ramp-1",
    "highway_lane_id": "main-1", "conflict_point_source": "synthetic diagnostic merge",
}
rows = []
for i in range(FRAME_COUNT):
    t = i / FRAME_RATE
    rows.append({
        "frame": i, "time_s": t,
        "ego_x_m": 5*t, "ego_y_m": 3.0, "ego_vx_mps": 5.0, "ego_vy_mps": 0.0, "ego_radius_m": 1.0,
        "through_x_m": 10*t, "through_y_m": 0.0, "through_vx_mps": 10.0,
        "through_vy_mps": 0.0, "through_radius_m": 1.0,
        "ego_distance_to_conflict_m": max(0.0, 100 - 5*t),
        "through_distance_to_conflict_m": max(0.0, 120 - 10*t),
        "through_on_highway": True, "ego_yielding": 100 <= i < 200,
    })
assert control_request("earlier_yield", 4.0)["yield_request"]
assert not control_request("later_yield", 4.0)["yield_request"]
assert control_request("later_yield", 2.0)["yield_request"]
reject(lambda: control_request("legal_hazard", 4.0), "unknown yield")
m = measure_trace(rows, network)
assert m["frames"] == 600 and m["duration_s"] == 30.0
assert m["observed_yield_frames"] == 100
assert m["legal_immediate_hazard_conclusion"] is None
reject(lambda: measure_trace(rows[:-1], network), "600 frames")
bad = [dict(row) for row in rows]
bad[20]["time_s"] = 7.0
reject(lambda: measure_trace(bad, network), "20 Hz join")
bad = [dict(row) for row in rows]
bad[20]["through_on_highway"] = None
reject(lambda: measure_trace(bad, network), "highway-presence")
bad = [dict(row, through_on_highway=False) for row in rows]
reject(lambda: measure_trace(bad, network), "approaching highway traffic")
bad_network = dict(network, controlled_access_source="")
reject(lambda: measure_trace(rows, bad_network), "sourced distinct")
exit_network = dict(network, route_kind="exit")
assert measure_trace(rows, exit_network)["route_kind"] == "exit"
print("PASS: 600-frame controlled-access yield and gap positive/negative CPU proof")
