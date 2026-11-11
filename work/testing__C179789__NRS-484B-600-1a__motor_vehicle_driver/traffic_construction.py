"""Spawn an actual Native lead vehicle on the source-reviewed ego lane."""

from contextlib import contextmanager
import math


def _project(point,tangent):
    return point.x*tangent[0]+point.y*tangent[1]


@contextmanager
def spawn_lead_traffic(world,ego,blueprint,transform,road_id,lane_id,lane_forward_xy):
    tx,ty=map(float,lane_forward_xy)
    norm=math.hypot(tx,ty)
    if not math.isfinite(norm) or norm<=0:raise ValueError("Invalid source lane direction")
    tangent=(tx/norm,ty/norm)
    lead=world.try_spawn_actor(blueprint,transform)
    if lead is None:raise ValueError("Native lead-traffic spawn failed")
    try:
        waypoint=world.get_map().get_waypoint(lead.get_location(),project_to_road=False)
        if waypoint is None or (waypoint.road_id,waypoint.lane_id)!=(road_id,lane_id):
            raise ValueError("Lead traffic outside source-reviewed ego lane")
        ego_position=_project(ego.get_location(),tangent)
        lead_position=_project(lead.get_location(),tangent)
        ego_half=float(ego.bounding_box.extent.x)
        lead_half=float(lead.bounding_box.extent.x)
        gap=lead_position-lead_half-(ego_position+ego_half)
        if not math.isfinite(gap) or gap<=0:
            raise ValueError("Lead vehicle does not begin ahead without overlap")
        yield {"actor":lead,"initial_longitudinal_body_gap_m":gap,
               "road_id":road_id,"lane_id":lane_id}
    finally:
        lead.destroy()
