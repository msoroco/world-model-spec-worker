"""Native-facing right-turn indicator policy for the C378304 route.

Progress is measured from the authored approach start in metres. Native
readback, route geometry and captured frames decide what actually happened.
"""

import math

APPROACH_M = 120.0
RIGHT_MASK = 16
CASE_DISTANCES_M = {
    "zone_right_below_100ft": 25.0,
    "zone_right_at_100ft": 30.48,
    "zone_right_above_100ft": 38.0,
    "zone_right_interrupted": 38.0,
    "zone_right_wet": 30.48,
    "other_area_right_at_300ft": 91.44,
}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


class RightTurnPolicy:
    def __init__(self, case_id):
        name = str(case_id).split("__")[-1]
        if name not in CASE_DISTANCES_M:
            raise ValueError("Unknown exact C378304 right-turn case")
        self.case_id = case_id
        self.name = name
        self.distance_m = CASE_DISTANCES_M[name]
        self.last_progress = None
        self.first_on_progress = None
        self.interruption_seen = False

    def requested_indicator(self, progress_m):
        if not _finite(progress_m) or not -1 <= progress_m <= APPROACH_M + 45:
            raise ValueError("Invalid Native route progress")
        if self.last_progress is not None and progress_m + 0.05 < self.last_progress:
            raise ValueError("Native right-turn route reversed")
        self.last_progress = progress_m
        on = progress_m >= APPROACH_M - self.distance_m
        # The interrupted comparison removes indication for a measured span
        # inside the last 100 feet. It must then be seen On again before turn.
        if self.name == "zone_right_interrupted" and 98 <= progress_m < 104:
            on = False
            self.interruption_seen = True
        if on and self.first_on_progress is None:
            self.first_on_progress = progress_m
        return on

    def apply(self, vehicle, light_state_type, progress_m):
        enabled = self.requested_indicator(progress_m)
        flag = light_state_type.RightBlinker
        current = vehicle.get_light_state()
        requested = current | flag if enabled else current & ~flag
        vehicle.set_light_state(requested)
        observed = vehicle.get_light_state()
        if bool(observed & flag) != enabled:
            raise ValueError("Native right indicator readback differs from request")
        return {"requested_right_indicator": enabled,
                "readback_right_indicator": bool(observed & flag),
                "ego_light_mask": int(observed)}


def source_row(snapshot, ego, waypoint, light_state_type):
    """Capture the values required by the saved analyzer from one Native tick."""
    frame = snapshot.frame
    time_s = snapshot.timestamp.elapsed_seconds
    location = ego.get_transform().location
    yaw = ego.get_transform().rotation.yaw
    velocity = ego.get_velocity()
    light = ego.get_light_state()
    body = [[vertex.x, vertex.y] for vertex in
            ego.bounding_box.get_world_vertices(ego.get_transform())]
    if (type(frame) is not int or not _finite(time_s)
            or not all(_finite(v) for v in (location.x, location.y, yaw, velocity.x,
                                            velocity.y, velocity.z))
            or type(waypoint.road_id) is not int or type(waypoint.lane_id) is not int
            or len(body) < 4 or any(not all(_finite(value) for value in point)
                                     for point in body)):
        raise ValueError("Incomplete Native right-turn source tick")
    return {"frame": frame, "time_s": time_s,
            "ego_position_xy_m": [location.x, location.y],
            "ego_speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
            "ego_heading_deg": yaw,
            "ego_body_vertices_xy_m": body,
            "native_road_id": waypoint.road_id, "native_lane_id": waypoint.lane_id,
            "right_indicator": bool(light & light_state_type.RightBlinker),
            "ego_light_mask": int(light)}
