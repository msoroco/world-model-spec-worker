"""Request and read back the Native right blinker without clearing other lights."""


def set_right_indicator(vehicle, light_state_type, enabled):
    current = vehicle.get_light_state()
    flag = light_state_type.RightBlinker
    value = current | flag if enabled else current & ~flag
    vehicle.set_light_state(value)
    return {"requested_right_indicator": bool(enabled),
            "readback_right_indicator": bool(vehicle.get_light_state() & flag)}
