"""Select a real adjacent Native driving lane and its marked boundary."""

import math

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


def step_toward_marked_lane(ego, selected, case_id, body_left_source_lane,
                            light_states, control_factory, target_speed_mps=5.0):
    """Issue one bounded Native control step toward the verified adjacent lane.

    The target is a route waypoint, not a claimed safe gap or legal decision.
    The caller must retain the original actor, marking and lamp observations.
    """
    if selected.get("direction") not in ("left", "right") or selected.get("target") is None:
        raise ValueError("Verified adjacent lane selection required")
    if not isinstance(target_speed_mps, (int, float)) or isinstance(target_speed_mps, bool):
        raise ValueError("Finite target speed required")
    if not math.isfinite(target_speed_mps) or not 0 < target_speed_mps <= 15:
        raise ValueError("Bounded target speed required")
    suffix=case_id[len(CASE_PREFIX):] if case_id.startswith(CASE_PREFIX) else ""
    if suffix not in SIGNAL_CASES or SIGNAL_CASES[suffix][0]!=selected["direction"]:
        raise ValueError("Exact case and selected lane direction differ")
    target=selected["target"].transform.location
    transform=ego.get_transform()
    here=transform.location
    dx,dy=target.x-here.x,target.y-here.y
    if not all(math.isfinite(v) for v in (dx,dy,transform.rotation.yaw)) or math.hypot(dx,dy)<0.25:
        raise ValueError("Distinct finite Native route target required")
    desired=math.atan2(dy,dx)
    yaw=math.radians(transform.rotation.yaw)
    error=math.atan2(math.sin(desired-yaw),math.cos(desired-yaw))
    steer=max(-0.7,min(0.7,error/1.2))
    velocity=ego.get_velocity()
    speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    if not math.isfinite(speed):
        raise ValueError("Finite Native speed required")
    throttle=0.25 if speed<target_speed_mps else 0.0
    brake=0.2 if speed>target_speed_mps+2 else 0.0
    signal=apply_indicator(ego,light_states,indicator_command(case_id,body_left_source_lane))
    control=control_factory(throttle=throttle,steer=steer,brake=brake,
                            reverse=False,manual_gear_shift=False)
    ego.apply_control(control)
    return {"control":control,"signal":signal,"target_lane_id":selected.get("target_lane_id"),
            "heading_error_rad":error,"observed_speed_mps":speed,
            "legal_safety_ascertainment":"unresolved"}
