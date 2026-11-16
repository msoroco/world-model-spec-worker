"""20 Hz capture schedule for requested red-curb duration boundary cases.

These counts are controller and recorder requests. Saved analysis must still
measure the retained Native frames before assigning a boundary observation.
"""
from decimal import Decimal, InvalidOperation

RATE_HZ = 20
THIRTY_MINUTES_S = Decimal('1800')


def plan(case, approach_frames=120):
    if not isinstance(case, dict) or not isinstance(case.get('case_id'), str):
        raise ValueError('Missing exact exception case')
    if type(approach_frames) is not int or approach_frames <= 0:
        raise ValueError('Invalid approach frame count')
    try:
        duration = Decimal(str(case['requested_stationary_duration_s']))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        raise ValueError('Missing requested stationary duration') from None
    if not duration.is_finite() or duration <= 0:
        raise ValueError('Invalid requested stationary duration')
    intervals = duration * RATE_HZ
    if intervals != intervals.to_integral_value():
        raise ValueError('Requested duration is off the 20 Hz frame grid')
    stationary_frames = int(intervals) + 1
    first = approach_frames
    last = first + stationary_frames - 1
    return {'case_id': case['case_id'], 'rate_hz': RATE_HZ,
            'requested_stationary_duration_s': float(duration),
            'requested_boundary': ('below' if duration < THIRTY_MINUTES_S else
                                   'at' if duration == THIRTY_MINUTES_S else 'above'),
            'approach_frames': approach_frames,
            'stationary_first_frame': first,
            'stationary_last_frame': last,
            'stationary_frames': stationary_frames,
            'capture_frames': last + 1,
            'source_kind': 'controller_request',
            'original_native_observed': False}
