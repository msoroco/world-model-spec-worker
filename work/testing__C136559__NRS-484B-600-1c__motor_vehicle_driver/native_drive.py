"""Native vehicle construction and route-following control for C136559.

The operator must supply reviewed map, road, lane and road-authority sources.
No packaged Town route is silently treated as an alley or public highway.
"""

from contextlib import contextmanager

from route_construction import select_corridor
from route_following import RouteFollower
from speed_controller import PostedSpeedController


REQUIRED = ("native_map_id", "reviewed_road_id", "reviewed_lane_id",
            "minimum_length_m", "subject_blueprint_id", "route_source",
            "narrow_road_source", "posting_source", "road_authority_source")


def validate_context(context):
    for key in REQUIRED:
        if context.get(key) in (None, ""):
            raise ValueError("Missing source-reviewed corridor context: " + key)
    if type(context["reviewed_road_id"]) is not int or type(context["reviewed_lane_id"]) is not int:
        raise ValueError("Native road and lane IDs must be integers")
    if type(context["minimum_length_m"]) not in (int, float) or context["minimum_length_m"] <= 0:
        raise ValueError("Positive minimum corridor length required")
    return context


@contextmanager
def construct_vehicle(world, context):
    """Spawn on a measured uninterrupted lane; destroy only the owned actor."""
    validate_context(context)
    native_map = world.get_map()
    if native_map.name != context["native_map_id"]:
        raise ValueError("Native map identity differs from reviewed corridor")
    corridor = select_corridor(
        native_map, native_map.get_spawn_points(),
        reviewed_road_id=context["reviewed_road_id"],
        reviewed_lane_id=context["reviewed_lane_id"],
        minimum_length_m=context["minimum_length_m"])
    blueprint = world.get_blueprint_library().find(context["subject_blueprint_id"])
    if blueprint is None:
        raise ValueError("Source-reviewed vehicle blueprint unavailable")
    vehicle = world.try_spawn_actor(blueprint, corridor["start"])
    if vehicle is None:
        raise ValueError("Native vehicle spawn failed on reviewed corridor")
    try:
        yield vehicle, corridor
    finally:
        vehicle.destroy()


class NativeDrive:
    def __init__(self, corridor, target_mph, control_factory, *, gain=0.12):
        self.follower = RouteFollower(corridor["waypoints"])
        self.controller = PostedSpeedController(target_mph, control_factory, gain=gain)

    def step(self, vehicle):
        route = self.follower.step(vehicle)
        command = self.controller.step(
            vehicle, steering=route["steering"],
            remaining_route_m=route["distance_to_route_end_m"])
        return {**route, **command}
