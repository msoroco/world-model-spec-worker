"""Source-trace measurements for NRS 484B.223(1)(b); no legal verdict.

Each row is a retained Native sample, never a supplied derived channel. Diagnostic
fixtures use the same schema but are labelled synthetic_native_sample.
"""
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20


def measure(rows, source_kind):
    if len(rows) != FRAMES:
        raise ValueError('600 synchronized Native source samples required')
    if source_kind not in ('original_native', 'synthetic_native_sample'):
        raise ValueError('Source kind missing')
    departure = None
    signal_start = None
    last_signal = False
    minimum_gap = math.inf
    minimum_ttc = math.inf
    lane_count = None
    for i, row in enumerate(rows):
        if row.get('source_kind') != source_kind or row.get('video_frame') != i:
            raise ValueError('Source/frame identity mismatch')
        if row.get('time_s') != i / RATE:
            raise ValueError('Source time join mismatch')
        if row.get('native_frame') is None:
            raise ValueError('Missing original Native frame key')
        if row.get('same_direction_marked_lane_count') is None:
            raise ValueError('Marked-lane source missing')
        if lane_count is None:
            lane_count = row['same_direction_marked_lane_count']
        if row['same_direction_marked_lane_count'] != lane_count:
            raise ValueError('Lane-count context changed')
        offset = row.get('ego_lateral_offset_from_occupied_lane_center_m')
        halfwidth = row.get('occupied_lane_half_width_m')
        halfbody = row.get('ego_body_half_width_m')
        signal = row.get('target_direction_indicator_on')
        gap = row.get('target_lane_min_surface_gap_m')
        closing = row.get('target_lane_closing_speed_mps')
        if (not all(type(v) in (int, float) and math.isfinite(v) for v in
                    (offset, halfwidth, halfbody, gap, closing)) or
                not 0 < halfbody < halfwidth or gap < 0 or closing < 0 or
                type(signal) is not bool):
            raise ValueError('Invalid original source geometry or signal')
        if signal and not last_signal:
            signal_start = i
        last_signal = signal
        if departure is None and abs(offset) + halfbody > halfwidth:
            departure = i
        minimum_gap = min(minimum_gap, gap)
        if closing > 0:
            minimum_ttc = min(minimum_ttc, gap / closing)
    departure_row = rows[departure] if departure is not None else None
    signal_before = (departure is not None and signal_start is not None and
                     signal_start < departure and bool(departure_row['target_direction_indicator_on']))
    # Gap and TTC are engineering observations. Neither establishes that a driver
    # actually ascertained safety or that a particular maneuver was legally safe.
    return {
        'source_kind': source_kind,
        'frames': FRAMES,
        'rate_hz': RATE,
        'same_direction_marked_lane_count': lane_count,
        'activation_observed': lane_count >= 2 and departure is not None,
        'first_body_departure_frame': departure,
        'signal_start_frame': signal_start,
        'signal_precedes_departure': signal_before,
        'signal_lead_s': (departure - signal_start) / RATE if signal_before else None,
        'gap_at_departure_m': departure_row['target_lane_min_surface_gap_m'] if departure_row else None,
        'ttc_at_departure_s': (departure_row['target_lane_min_surface_gap_m'] /
                               departure_row['target_lane_closing_speed_mps']
                               if departure_row and departure_row['target_lane_closing_speed_mps'] > 0
                               else None),
        'minimum_gap_m': minimum_gap,
        'minimum_finite_ttc_s': minimum_ttc if math.isfinite(minimum_ttc) else None,
        'driver_safety_ascertainment': 'unobserved',
        'legal_verdict': None,
    }


def read_trace(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]
