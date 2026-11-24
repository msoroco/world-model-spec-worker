"""Calibratable Native lamp stage for the zero-frame signal-boundary candidate.

The stage tick is a construction target. Original saved observations decide
whether signal onset actually coincided with complete-body lane departure.
"""

from native_lane_construction import apply_indicator


def apply_stage(ego, light_states, tick_index, stage_tick, frame_count=900):
    if type(tick_index) is not int or type(stage_tick) is not int or type(frame_count) is not int:
        raise ValueError("Integer Native capture stage required")
    if frame_count != 900 or not 0 <= tick_index < frame_count or not 1 <= stage_tick < frame_count:
        raise ValueError("Bounded 900-frame signal stage required")
    command = "left" if tick_index >= stage_tick else "off"
    return apply_indicator(ego, light_states, command)
