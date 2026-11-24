"""Select a real adjacent Native driving lane and its marked boundary."""

CASE_PREFIX="testing__C144550__NRS-484B-223-1b__motor_vehicle_driver__"
SIGNAL_CASES={
    "left_signal_before_clear_gap":("left","before"),
    "left_signal_late_clear_gap":("left","late"),
    "left_wrong_signal_clear_gap":("left","wrong"),
    "left_signal_before_close_gap":("left","before"),
    "right_signal_before_clear_gap":("right","before"),
}


def select_adjacent_marked_lane(waypoint, direction, lane_type_driving):
    if direction not in ("left","right"):
        raise ValueError("Lane-change direction must be left or right")
    neighbor=waypoint.get_left_lane() if direction=="left" else waypoint.get_right_lane()
    if neighbor is None or neighbor.lane_type!=lane_type_driving:
        raise ValueError("No adjacent Native driving lane in requested direction")
    if neighbor.road_id!=waypoint.road_id or neighbor.lane_id==waypoint.lane_id:
        raise ValueError("Adjacent lane road/identity mismatch")
    if waypoint.lane_id==0 or neighbor.lane_id==0 or (waypoint.lane_id>0)!=(neighbor.lane_id>0):
        raise ValueError("Adjacent lane travels in the opposite direction")
    marking=waypoint.left_lane_marking if direction=="left" else waypoint.right_lane_marking
    if marking is None or str(marking.type).lower().endswith("none"):
        raise ValueError("No visible Native lane marking at crossing boundary")
    return {"source":waypoint,"target":neighbor,"marking":marking,
            "direction":direction,"source_lane_id":waypoint.lane_id,
            "target_lane_id":neighbor.lane_id}


def indicator_command(case_id, body_left_source_lane):
    """Choose the planned signal; original frames still decide what displayed."""
    if type(body_left_source_lane) is not bool:
        raise ValueError("Original body-departure observation required")
    if not case_id.startswith(CASE_PREFIX) or case_id[len(CASE_PREFIX):] not in SIGNAL_CASES:
        raise ValueError("Unknown exact lane-change case")
    direction,policy=SIGNAL_CASES[case_id[len(CASE_PREFIX):]]
    if policy=="late" and not body_left_source_lane:return "off"
    if policy=="wrong":return "right" if direction=="left" else "left"
    return direction


def apply_indicator(ego, light_states, command):
    """Set turn lamps without clearing unrelated Native vehicle lights."""
    if command not in ("off","left","right"):
        raise ValueError("Invalid indicator command")
    left=int(light_states.LeftBlinker)
    right=int(light_states.RightBlinker)
    current=int(ego.get_light_state())
    state=current & ~(left|right)
    if command=="left":state|=left
    if command=="right":state|=right
    ego.set_light_state(light_states(state))
    return {"requested_indicator":command,"readback_state":int(ego.get_light_state())}
