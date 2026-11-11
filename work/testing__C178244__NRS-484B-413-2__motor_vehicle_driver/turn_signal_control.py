"""Apply the Native left blinker for a source-reviewed left-turn route."""


def set_left_indicator(vehicle, light_state_type, enabled):
    current = vehicle.get_light_state()
    flag = light_state_type.LeftBlinker
    value = current | flag if enabled else current & ~flag
    vehicle.set_light_state(value)
    return {"requested_left_indicator": bool(enabled), "readback_left_indicator":
            bool(vehicle.get_light_state() & flag)}
