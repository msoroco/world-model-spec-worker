"""Build another road participant and inventory devices at the shared crossing."""
from contextlib import contextmanager

def verify_uncontrolled_crossing(world, crossing_id, entrance_road_lanes, excluded_device_ids=()):
    if len(entrance_road_lanes)<2 or len({road for road,_ in entrance_road_lanes})<2:
        raise ValueError("Different highway entrance roads required")
    devices=list(world.get_actors().filter("traffic.traffic_light*"))
    devices+=list(world.get_actors().filter("traffic.stop*"))
    devices+=list(world.get_actors().filter("traffic.yield*"))
    excluded=set(excluded_device_ids)
    controlling=[]
    for actor in devices:
        if actor.id in excluded:continue
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
