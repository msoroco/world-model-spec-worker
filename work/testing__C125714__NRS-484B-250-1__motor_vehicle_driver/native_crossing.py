"""Build another road participant and inventory devices at the shared crossing."""
from contextlib import contextmanager
from median_geometry import plan_approaches

def verify_uncontrolled_crossing(world, crossing_id, entrance_road_lanes):
    if len(entrance_road_lanes)<2 or len({road for road,_ in entrance_road_lanes})<2:
        raise ValueError("Different highway entrance roads required")
    devices=list(world.get_actors().filter("traffic.traffic_light*"))
    devices+=list(world.get_actors().filter("traffic.stop*"))
    devices+=list(world.get_actors().filter("traffic.yield*"))
    controlling=[]
    for actor in devices:
        if not hasattr(actor,"get_affected_lane_waypoints"):
            raise ValueError("Official device geometry requires source review")
        if any(wp.road_id==road and wp.lane_id==lane for wp in actor.get_affected_lane_waypoints() for road,lane in entrance_road_lanes):
            controlling.append(actor.id)
    if controlling:raise ValueError("Official device governs an entrance")
    return {"crossing_id":crossing_id,"entrance_road_lanes":list(entrance_road_lanes),"native_controlling_device_ids":[]}

@contextmanager
def spawn_other(world, blueprint, transform):
    actor=world.try_spawn_actor(blueprint,transform)
    if actor is None:raise ValueError("Other participant Native spawn failed")
    try:yield actor
    finally:actor.destroy()


@contextmanager
def construct_crossing_candidate(world, ego_approach, ego_entry,
                                 other_approach, other_entry, other_blueprint,
                                 crossing_polygon_xy_m, crossing_id,
                                 polygon_source, entrance_source):
    """Own the other actor after geometry and official-device checks pass."""
    plan = plan_approaches(world.get_map(), ego_approach, ego_entry,
                           other_approach, other_entry, crossing_polygon_xy_m,
                           crossing_id, polygon_source, entrance_source)
    lanes = [(plan["approaches"][role]["road_id"],
              plan["approaches"][role]["lane_id"]) for role in ("ego", "other")]
    plan["device_inventory"] = verify_uncontrolled_crossing(world, crossing_id, lanes)
    with spawn_other(world, other_blueprint, other_approach) as other:
        yield plan, other
