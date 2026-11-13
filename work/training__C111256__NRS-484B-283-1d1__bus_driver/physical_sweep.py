"""Physical hold-margin sweep for the Walk judgment; no legal labels.

The range samples the existing controller's 0 < margin <= 5 m engineering
domain. It is a proposed coverage grid, not a statutory right-of-way cutoff.
"""
from __future__ import annotations

import math

from controller import EngineeringKnobs, PathController, WalkFrame, WalkYieldController
from geometry import CROSSWALK_NEAR_Y_M, check as geometry_check, route

MARGINS_M = (0.5, 1.0, 1.5, 2.0)
SAMPLE_FRONT_Y_M = (-13.25, -12.25, -11.75)


def request_grid() -> list[dict]:
    """Exercise every fixed setpoint at source-shaped body positions."""
    geometry_check()
    rows = []
    for margin in MARGINS_M:
        controller = WalkYieldController(
            PathController(route(), 3.8, 35, EngineeringKnobs()),
            policy='yield_request', crosswalk_y_m=CROSSWALK_NEAR_Y_M,
            hold_margin_m=margin)
        for index, front_y in enumerate(SAMPLE_FRONT_Y_M):
            frame = WalkFrame(
                native_frame=100 + index, signal_actor_id=620,
                pedestrian_actor_id=720, display='Walk',
                pedestrian_facing_signal=True, pedestrian_in_crosswalk=True,
                pedestrian_xy_m=(1.75, CROSSWALK_NEAR_Y_M),
                bus_front_y_m=front_y, provenance='authored_display_request')
            command = controller.step(
                observation=frame, position_xy_m=(1.75, front_y - 3),
                yaw_rad=math.pi / 2, speed_mps=3, dt_s=.05)
            rows.append({'setpoint_margin_m': margin,
                         'source_shaped_front_y_m': front_y,
                         'hold_requested': command['hold_requested'],
                         'physical_yield_observed': command['physical_yield_observed'],
                         'legal_outcome_claimed': command['legal_outcome_claimed']})
    return rows


def measured_hold_margin(samples: list[dict], *, diagnostic: bool = False) -> dict:
    """Measure first requested hold from intact original Native body/control rows.

    This is a physical coverage observable only. Original signal pixels,
    governance and legal exception applicability are separate reviews.
    """
    if len(samples) != 480:
        raise ValueError('Hold-margin measurement requires all 480 Native rows')
    frames, times, held = [], [], []
    for row in samples:
        frame, time_s = row.get('native_frame'), row.get('time_s')
        if not isinstance(frame, int) or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
            raise ValueError('Invalid Native frame/time')
        frames.append(frame); times.append(time_s)
        required_provenance = 'synthetic_native_sample' if diagnostic else 'native_measured'
        if row.get('speed_provenance') != required_provenance:
            raise ValueError('Hold-margin source is not original Native measurement')
        body = row.get('bus_body_xy_m')
        if not isinstance(body, list) or len(body) != 4 or any(
                not isinstance(p, list) or len(p) != 2 or
                any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in p)
                for p in body):
            raise ValueError('Missing original four-corner bus body')
        command = row.get('controller_request')
        if not isinstance(command, dict) or type(command.get('hold_requested')) is not bool:
            raise ValueError('Missing source controller hold request')
        if command['hold_requested']:
            held.append((frame, time_s, CROSSWALK_NEAR_Y_M - max(p[1] for p in body)))
    if any(b <= a for a, b in zip(frames, frames[1:])) or any(
            b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Native frame/time order broken')
    if not held:
        raise ValueError('No requested hold in original Native rows')
    frame, time_s, margin = held[0]
    return {'observable': 'crosswalk_hold_margin_m', 'unit': 'm',
            'value': margin, 'native_frame': frame, 'time_s': time_s,
            'method': 'first requested hold: marked crosswalk y minus measured bus body front y',
            'diagnostic': diagnostic, 'legal_outcome_claimed': False}
