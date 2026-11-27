"""Synthetic CPU fixtures for original-readback binding invariants."""

from copy import deepcopy

from acquisition import VIEWS, bind_original


def reject(rows, cameras, context, phrase):
    try:
        bind_original(rows, cameras, context, "earlier_yield")
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


context = {
    "route_kind": "entry", "map_source": "native_opendrive_readback",
    "map_sha256": "a" * 64, "actor_inventory_source": "synthetic_fixture_inventory",
    "controlled_access_designation_verified": False,
    "approaching_vehicle_ids": ["near", "far"],
}
rows = []
cameras = []
for i in range(600):
    t = i / 20
    x = -70 + 8 * t
    ego_road = 13 if x < 0 else 2 if x < 20 else 4
    ego_y = -20 + (x + 70) * 20 / 70 if x < 0 else 0
    ego = {"center_xy_m": [x, ego_y], "velocity_xy_mps":
           [8, 8 * 20 / 70] if x < 0 else [8, 0],
           "radius_m": 1.2, "road_id": ego_road, "lane_id": -1}
    traffic = {}
    for name, start in (("near", -110), ("far", -170)):
        other_x = start + 10 * t
        traffic[name] = {"center_xy_m": [other_x, -1.75],
                         "velocity_xy_mps": [10, 0], "radius_m": 1.2,
                         "road_id": 1 if other_x < 0 else 2 if other_x < 20 else 4,
                         "lane_id": -1}
    rows.append({"frame": i, "native_frame": 1000 + i, "time_s": t,
                 "ego": ego, "traffic": traffic, "ego_yielding": i < 200})
    cameras.append({"frame": 1000 + i,
                    "views": {view: 1000 + i for view in VIEWS}})

result = bind_original(rows, cameras, context, "earlier_yield")
assert result["frames"] == 600 and result["camera_views"] == list(VIEWS)
assert result["measurements"]["traffic_present_frames"] > 0
assert result["measurements"]["legal_immediate_hazard_conclusion"] is None
assert result["controlled_access_designation_verified"] is False
assert result["original_source_sha256"] == bind_original(
    rows, cameras, context, "later_yield")["original_source_sha256"]

bad = deepcopy(rows)
del bad[20]["traffic"]["far"]
reject(bad, cameras, context, "inventory differs")
bad = deepcopy(rows)
bad[20]["traffic"]["near"]["road_id"] = 3
reject(bad, cameras, context, "left highway")
bad = deepcopy(rows)
bad[20]["ego"]["road_id"] = 9
reject(bad, cameras, context, "left access")
bad = deepcopy(rows)
for row in bad:
    row["ego"]["road_id"] = 13
reject(bad, cameras, context, "traversal not observed")
bad = deepcopy(cameras)
bad[20]["views"].pop("reference_corner")
reject(rows, bad, context, "four exact")
bad = deepcopy(cameras)
bad[20]["views"]["reference_corner"] += 1
reject(rows, bad, context, "camera frame identity")
bad = deepcopy(context)
bad["controlled_access_designation_verified"] = True
reject(rows, cameras, bad, "cannot establish legal designation")
bad = deepcopy(context)
bad["actor_inventory_source"] = ""
reject(rows, cameras, bad, "actor inventory source")
print("PASS: 600-frame original Native/camera source binding, 8 negatives, legal status unresolved")
