"""Source-derived red-curb exception facts; no statutory verdicts.

Call with retained Native frame rows, map/sign readback, and recorded activity
events. A complete 20 Hz stationary interval is required to report its duration.
"""
from decimal import Decimal, InvalidOperation
from math import hypot, isfinite

STATIONARY_MPS = Decimal('0.1')  # engineering detector, not a legal threshold
MAX_FRAME_GAP_S = Decimal('0.051')
THIRTY_MINUTES_S = Decimal('1800')
VALID_EVENTS = ('passenger_loading', 'passenger_unloading',
                'business_activity', 'mail_deposit')


def number(value, field):
    if isinstance(value, bool):
        raise ValueError('Invalid numeric source: ' + field)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Invalid numeric source: ' + field) from None
    if not result.is_finite():
        raise ValueError('Nonfinite numeric source: ' + field)
    return result


def measure(frame_rows, context, events):
    if not isinstance(context, dict) or context.get('source_kind') not in (
            'native', 'original_native', 'synthetic_native_sample'):
        raise ValueError('Missing source provenance')
    kind = context['source_kind']
    curb = context.get('red_curb')
    if not isinstance(curb, dict) or curb.get('paint_color') != 'red':
        raise ValueError('Missing red-paint readback')
    start = number(curb.get('start_x_m'), 'red start')
    end = number(curb.get('end_x_m'), 'red end')
    curb_y = number(curb.get('curb_y_m'), 'curb y')
    if end <= start:
        raise ValueError('Invalid red-paint extent')
    sign = context.get('sign_readback')
    if not isinstance(sign, dict) or type(sign.get('present')) is not bool or \
            not isinstance(sign.get('displayed_classes'), list) or \
            any(not isinstance(item, str) or not item for item in sign['displayed_classes']) or \
            (not sign['present'] and sign['displayed_classes']):
        raise ValueError('Missing sign readback')
    sign_x = number(sign.get('center_x_m'), 'sign x') if sign['present'] else None
    sign_over_red = (start <= sign_x <= end) if sign_x is not None else None
    vehicle = context.get('vehicle_readback')
    if not isinstance(vehicle, dict) or not vehicle.get('native_blueprint') or not vehicle.get('declared_service_class'):
        raise ValueError('Missing vehicle identity readback')
    mailbox = context.get('mailbox_readback')
    if not isinstance(mailbox, dict) or type(mailbox.get('present')) is not bool:
        raise ValueError('Missing mail-drop readback')
    if mailbox['present']:
        box_x = number(mailbox.get('center_x_m'), 'mailbox x')
        box_y = number(mailbox.get('center_y_m'), 'mailbox y')
        mailbox_distance = hypot(float(box_x - max(start, min(box_x, end))),
                                 float(box_y - curb_y))
        if not isfinite(mailbox_distance):
            raise ValueError('Invalid mailbox geometry')
    else:
        mailbox_distance = None
    first = last = previous = None
    frames = 0
    for row in frame_rows:
        if row.get('source_kind') != kind:
            raise ValueError('Mixed frame provenance')
        if row.get('frame') != frames:
            raise ValueError('Missing or reordered Native frame')
        t = number(row.get('time_s'), 'frame time')
        if previous is not None and not (Decimal(0) < t - previous <= MAX_FRAME_GAP_S):
            raise ValueError('Incomplete 20 Hz source interval')
        body = row.get('ego_body_native_xy_m')
        velocity = row.get('velocity_native_xyz_mps')
        if not isinstance(body, list) or len(body) < 4 or not isinstance(velocity, list) or len(velocity) != 3:
            raise ValueError('Missing Native body or velocity')
        xs = [number(point[0], 'body x') for point in body]
        ys = [number(point[1], 'body y') for point in body]
        speed2 = sum(number(axis, 'velocity') ** 2 for axis in velocity)
        on_red = (min(xs) <= end and max(xs) >= start and
                  min(ys) <= curb_y <= max(ys))
        if on_red and speed2 <= STATIONARY_MPS ** 2:
            if first is None:
                first = t
            last = t
        elif first is not None:
            raise ValueError('Stationary red-curb interval interrupted')
        previous = t
        frames += 1
    if frames < 2 or first is None or last is None:
        raise ValueError('No measured stationary red-curb interval')
    duration = last - first
    measured_events = []
    for event in events:
        if event.get('source_kind') != kind or event.get('name') not in VALID_EVENTS or \
                not isinstance(event.get('source'), str) or not event['source']:
            raise ValueError('Invalid activity source')
        began = number(event.get('start_time_s'), 'event start')
        finished = number(event.get('end_time_s'), 'event end')
        if began < first or finished > last or finished < began:
            raise ValueError('Activity outside measured red-curb interval')
        measured_events.append({'name': event['name'],
                                'duration_s': float(finished - began),
                                'source': event.get('source')})
    return {'format': 'c150142-exception-observation-v1',
            'source_kind': kind, 'frames': frames,
            'red_curb_stationary_duration_s': float(duration),
            'duration_relative_to_30_minutes':
                'below' if duration < THIRTY_MINUTES_S else
                'at' if duration == THIRTY_MINUTES_S else 'above',
            'displayed_sign_classes': sign['displayed_classes'],
            'sign_present': sign['present'],
            'sign_center_x_m': float(sign_x) if sign_x is not None else None,
            'sign_over_red_extent': sign_over_red,
            'native_blueprint': vehicle['native_blueprint'],
            'declared_service_class': vehicle['declared_service_class'],
            'mailbox_present': mailbox['present'],
            'mailbox_curb_distance_m': mailbox_distance,
            'recorded_activity_events': measured_events,
            'statutory_exception_applies': None,
            'necessary_business_established': None,
            'expeditious_mail_deposit_established': None,
            'physical_acceptance_claimed': False,
            'legal_verdict': None}
