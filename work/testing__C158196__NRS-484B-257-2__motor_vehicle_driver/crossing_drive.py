"""Scripted two-vehicle motion for the C158196 signed-junction contrast.

Phase lengths are capture engineering values. They do not define a statutory
stop duration or an immediate-hazard threshold; original motion is measured.
"""


def apply_tick(ego, other, vehicle_control, tick, *, hold_ticks, ego_throttle=0.3,
               other_throttle=0.2):
    if any(type(value) is not int or value < 0 for value in (tick, hold_ticks)):
        raise ValueError("Invalid motion phase")
    if hold_ticks < 1:
        raise ValueError("A pre-entry hold phase is required")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or
           value <= 0 or value > 1 for value in (ego_throttle, other_throttle)):
        raise ValueError("Invalid vehicle throttle")
    if ego is other:
        raise ValueError("Ego and non-obligated traffic must be distinct actors")
    ego_hold = tick < hold_ticks
    ego.apply_control(vehicle_control(throttle=0.0 if ego_hold else ego_throttle,
                                      brake=1.0 if ego_hold else 0.0, steer=0.0))
    other.apply_control(vehicle_control(throttle=other_throttle, brake=0.0, steer=0.0))
    return {"tick": tick, "ego_hold_commanded": ego_hold,
            "other_vehicle_progress_commanded": True}
