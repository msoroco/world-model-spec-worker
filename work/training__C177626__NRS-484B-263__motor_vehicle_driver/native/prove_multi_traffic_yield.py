"""CPU proof of complete multi-actor access-point source and controller joins."""

from copy import deepcopy

from multi_traffic_yield import assess_trace, compare_policies


def reject(call, phrase):
    try:
        call()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


network = {
    "route_kind": "entry",
    "highway_source": "synthetic diagnostic lane map",
    "controlled_access_source": "synthetic diagnostic authority record",
    "access_lane_id": "ramp-1",
    "highway_lane_id": "main-1",
    "conflict_point_source": "synthetic diagnostic merge coordinate",
    "actor_inventory_source": "synthetic diagnostic actor registry",
    "approaching_vehicle_ids": ["through-near", "through-far"],
}
rows = []
for i in range(600):
    t = i / 20
    ego = {
        "x_m": 5 * t, "y_m": 3, "vx_mps": 5, "vy_mps": 0,
        "radius_m": 1, "distance_to_conflict_m": max(0, 100 - 5 * t),
    }
    near = {
        "x_m": 10 * t, "y_m": 0, "vx_mps": 10, "vy_mps": 0,
        "radius_m": 1, "distance_to_conflict_m": max(0, 110 - 10 * t),
        "on_highway": True, "approaching": i < 220,
    }
    far = {
        "x_m": 10 * t - 60, "y_m": 0, "vx_mps": 10, "vy_mps": 0,
        "radius_m": 1, "distance_to_conflict_m": max(0, 170 - 10 * t),
        "on_highway": True, "approaching": i < 340,
    }
    rows.append({
        "frame": i, "time_s": t, "ego": ego,
        "traffic": {"through-near": near, "through-far": far},
        "ego_yielding": i < 200,
    })

result = assess_trace(rows, network, "earlier_yield")
assert result["frames"] == 600 and result["duration_s"] == 30
assert result["traffic_present_frames"] == 340
assert result["approaching_vehicle_ids"] == ["through-near", "through-far"]
assert result["minimum_projected_arrival_gap_s_by_actor"]["through-near"] is not None
assert result["minimum_projected_arrival_gap_s_by_actor"]["through-far"] is not None
assert result["legal_immediate_hazard_conclusion"] is None
assert result["legal_reasonable_safety_conclusion"] is None
assert assess_trace(rows, dict(network, route_kind="exit"), "later_yield")["route_kind"] == "exit"
comparison = compare_policies(rows, network)
assert comparison["earlier_yield_request_frames"] == 340
assert comparison["later_yield_request_frames"] == 0
assert comparison["request_frame_difference"] == 340
assert comparison["legal_comparison_conclusion"] is None
changed = deepcopy(rows)
changed[15]["traffic"]["through-near"]["distance_to_conflict_m"] += 1
assert compare_policies(changed, network)["fixed_source_sha256"] != comparison["fixed_source_sha256"]

bad = deepcopy(rows)
del bad[15]["traffic"]["through-far"]
reject(lambda: assess_trace(bad, network, "earlier_yield"), "inventory missing")
bad = deepcopy(rows)
bad[15]["traffic"]["through-near"]["on_highway"] = False
reject(lambda: assess_trace(bad, network, "earlier_yield"), "highway source")
bad = deepcopy(rows)
bad[15]["traffic"]["through-near"]["distance_to_conflict_m"] = float("nan")
reject(lambda: assess_trace(bad, network, "earlier_yield"), "nonfinite raw")
bad = deepcopy(rows)
bad[15]["time_s"] = 1.0
reject(lambda: assess_trace(bad, network, "earlier_yield"), "20 Hz join")
bad = deepcopy(rows)
for row in bad:
    for actor in row["traffic"].values():
        actor["approaching"] = False
reject(lambda: assess_trace(bad, network, "earlier_yield"), "never observed")
reject(lambda: assess_trace(rows, dict(network, controlled_access_source=""), "earlier_yield"), "sourced controlled-access")
reject(lambda: assess_trace(rows, dict(network, highway_lane_id="ramp-1"), "earlier_yield"), "distinct access")
reject(lambda: assess_trace(rows, dict(network, approaching_vehicle_ids=["through-near"]), "earlier_yield"), "inventory missing")
reject(lambda: assess_trace(rows, network, "legal_hazard"), "unknown yield")
print("PASS: 600-frame entry/exit multi-vehicle yield source and controller CPU proof")
