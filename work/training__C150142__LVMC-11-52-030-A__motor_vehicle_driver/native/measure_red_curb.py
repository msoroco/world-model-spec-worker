"""Source-shaped red-curb occupancy measurement without a legal verdict.

The parked interval is an observed repeated body position, not a speed cutoff.
Paint and signage require separate Native and pixel evidence at delivery.
"""
import math

VIEWS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def measure(rows, frame_map, curb, expected_frames=240):
    require(type(expected_frames) is int and expected_frames >= 2 and
            len(rows) == len(frame_map) == expected_frames,
            'Missing synchronized capture frames')
    require(curb.get('paint_color') == 'red' and curb.get('source_kind') in
            {'native_readback', 'synthetic_native_sample'} and
            all(finite(curb.get(key)) for key in ('start_x_m', 'end_x_m', 'curb_y_m')) and
            curb['start_x_m'] < curb['end_x_m'],
            'Red curb extent lacks source-bound geometry')
    provenance = {row.get('source_kind') for row in rows}
    require(len(provenance) == 1 and provenance <=
            {'original_native', 'synthetic_native_sample'},
            'Actor positions have mixed or missing provenance')
    source_kind = next(iter(provenance))
    if source_kind == 'original_native':
        require(curb['source_kind'] == 'native_readback',
                'Original actor positions cannot use fixture curb paint')
    previous = None
    red_stopped = []
    stopped = []
    for index, (row, frame) in enumerate(zip(rows, frame_map)):
        require(row.get('frame') == frame.get('video_frame') == index and
                row.get('native_frame') == frame.get('native_frame') and
                set(frame.get('views', [])) == VIEWS,
                'Changed four-view actor/frame join')
        body = row.get('ego_body_native_xy_m')
        center = row.get('ego_center_native_xy_m')
        require(isinstance(body, list) and len(body) >= 4 and
                all(isinstance(point, list) and len(point) == 2 and
                    all(finite(v) for v in point) for point in body) and
                isinstance(center, list) and len(center) == 2 and
                all(finite(v) for v in center),
                'Missing measured ego body or center')
        is_stopped = previous == center if previous is not None else False
        previous = center
        if is_stopped:
            stopped.append(index)
        xs = [point[0] for point in body]
        ys = [point[1] for point in body]
        along_red = max(xs) >= curb['start_x_m'] and min(xs) <= curb['end_x_m']
        # A body touching the painted edge is observable; a legal curb-zone
        # conclusion still needs jurisdiction, signage and pixel review.
        touches_curb = min(ys) <= curb['curb_y_m'] <= max(ys)
        if is_stopped and along_red and touches_curb:
            red_stopped.append(index)
    return {'format': 'c150142-red-curb-observation-v1',
            'source_kind': source_kind, 'frames': expected_frames,
            'stopped_frame_ids': stopped,
            'red_curb_stopped_frame_ids': red_stopped,
            'red_curb_stop_or_park_observed': bool(red_stopped),
            'paint_color': 'red',
            'legal_verdict': None,
            'physical_acceptance_claimed': False}
