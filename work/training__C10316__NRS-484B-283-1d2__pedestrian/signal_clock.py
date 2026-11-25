"""Proposed frame-synchronized pedestrian countdown program, CPU only."""
import math


def frame_state(frame_index, zero_time_s, rate_hz=20, flash_hz=2):
    if type(frame_index) is not int or frame_index < 0:
        raise ValueError('Invalid source frame index')
    if rate_hz != 20 or flash_hz != 2 or type(zero_time_s) not in (int, float) or not math.isfinite(zero_time_s) or zero_time_s <= 0:
        raise ValueError('Invalid synchronized signal schedule')
    time_s = frame_index / rate_hz
    displayed = math.ceil(max(0.0, zero_time_s - time_s) - 1e-8)
    phase = (frame_index // (rate_hz // (2*flash_hz))) % 2
    return {'time_s': round(time_s, 2), 'displayed_countdown_s': displayed,
            'indication': 'dont_walk_flashing' if displayed > 0 else 'dont_walk_steady',
            'display_illuminated': bool(phase == 0) if displayed > 0 else True,
            'source_scope': 'authored_frame_program_not_original_pixels'}
