"""Inspect both intersecting Native roads for opposite-direction driving lanes.

Signed lane IDs are an engineering preflight, not proof of legal highway status
or the exact physical centerline; original map/camera review remains required.
"""


def verify_two_directional_roads(world, approach_road_id, outgoing_road_id,
                                 *, waypoint_spacing_m=2.0):
    if approach_road_id==outgoing_road_id:
        raise ValueError("Two intersecting road identities required")
    waypoints=world.get_map().generate_waypoints(waypoint_spacing_m)
    lanes={approach_road_id:set(),outgoing_road_id:set()}
    for waypoint in waypoints:
        if waypoint.road_id in lanes and str(waypoint.lane_type).lower().endswith("driving"):
            lanes[waypoint.road_id].add(waypoint.lane_id)
    for road_id,ids in lanes.items():
        if not any(i>0 for i in ids) or not any(i<0 for i in ids):
            raise ValueError("Opposite-direction Native driving lanes missing on road "+str(road_id))
    return {"approach_road_id":approach_road_id,"outgoing_road_id":outgoing_road_id,
            "native_lane_ids":{str(key):sorted(value) for key,value in lanes.items()},
            "legal_two_directional_status":"unresolved pending source review"}
