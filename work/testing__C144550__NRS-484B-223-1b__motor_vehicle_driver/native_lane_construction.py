"""Select a real adjacent Native driving lane and its marked boundary."""


def select_adjacent_marked_lane(waypoint, direction, lane_type_driving):
    if direction not in ("left","right"):
        raise ValueError("Lane-change direction must be left or right")
    neighbor=waypoint.get_left_lane() if direction=="left" else waypoint.get_right_lane()
    if neighbor is None or neighbor.lane_type!=lane_type_driving:
        raise ValueError("No adjacent Native driving lane in requested direction")
    if neighbor.road_id!=waypoint.road_id or neighbor.lane_id==waypoint.lane_id:
        raise ValueError("Adjacent lane road/identity mismatch")
    marking=waypoint.left_lane_marking if direction=="left" else waypoint.right_lane_marking
    if marking is None or str(marking.type).lower().endswith("none"):
        raise ValueError("No visible Native lane marking at crossing boundary")
    return {"source":waypoint,"target":neighbor,"marking":marking,
            "direction":direction,"source_lane_id":waypoint.lane_id,
            "target_lane_id":neighbor.lane_id}
