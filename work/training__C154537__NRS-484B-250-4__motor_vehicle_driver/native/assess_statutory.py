"""Saved-source measurements for the stop-reference and yielding alternatives.

This reports observed ordering only. It never decides whether a view is legally
clear or whether proceeding was cautious.
"""
from math import isfinite


def _number(value, name):
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError('Missing original measurement: ' + name)
    return value


def assess(survey, rows):
    if not rows:
        raise ValueError('Missing original motion history')
    line = survey.get('stop_line_present')
    crossing = survey.get('near_side_crosswalk_present')
    if type(line) is not bool or type(crossing) is not bool:
        raise ValueError('Stop-reference survey incomplete')
    if line:
        reference = 'marked_stop_line'
        point = _number(survey.get('stop_line_front_x_m'), 'stop line')
    elif crossing:
        if survey.get('sidewalk_derived_crosswalk_reviewed') is not True:
            raise ValueError('Sidewalk-derived crosswalk review missing')
        reference = 'near_side_crosswalk'
        point = _number(survey.get('crosswalk_near_edge_x_m'), 'near-side crosswalk')
    else:
        if survey.get('sidewalk_derived_crosswalk_reviewed') is not True:
            raise ValueError('Sidewalk-derived crosswalk review missing')
        reference = 'nearest_surveyed_view'
        samples = survey.get('driver_view_samples')
        if not isinstance(samples, list) or not samples:
            raise ValueError('Original driver-view samples missing')
        visible = [s.get('center_x_m') for s in samples
                   if s.get('approaching_traffic_visible') is True]
        if not visible:
            raise ValueError('No surveyed approaching-traffic view')
        point = max(_number(x, 'driver-view position') for x in visible)
    entry_point = _number(survey.get('intersection_entry_front_x_m'), 'intersection entry')
    bounds = survey.get('intersection_bounds_xy_m')
    if not isinstance(bounds, list) or len(bounds) != 4:
        raise ValueError('Original intersection bounds missing')
    xmin, ymin, xmax, ymax = [_number(value, 'intersection bound') for value in bounds]
    if xmin >= xmax or ymin >= ymax:
        raise ValueError('Original intersection bounds invalid')
    ego_stop = None
    other_stops = []
    entry = None
    other_inside_at_entry = False
    other_clear_after_entry = None
    previous_frame = -1
    for row in rows:
        frame = row.get('native_frame')
        if type(frame) is not int or frame <= previous_frame:
            raise ValueError('Original frame order differs')
        previous_frame = frame
        front = _number(row.get('ego_front_x_m'), 'ego front')
        center = _number(row.get('ego_center_x_m'), 'ego center')
        speed = _number(row.get('ego_speed_mps'), 'ego speed')
        other = row.get('other')
        if not isinstance(other, dict):
            raise ValueError('Other-vehicle original history missing')
        other_speed = _number(other.get('speed_mps'), 'other speed')
        vertices = other.get('body_xyz_m')
        if not isinstance(vertices, list) or len(vertices) != 8 or any(
                not isinstance(vertex, list) or len(vertex) != 3 for vertex in vertices):
            raise ValueError('Other-vehicle original body history missing')
        ox = [_number(vertex[0], 'other body x') for vertex in vertices]
        oy = [_number(vertex[1], 'other body y') for vertex in vertices]
        other_in = max(ox) >= xmin and min(ox) <= xmax and max(oy) >= ymin and min(oy) <= ymax
        other_before = max(oy) < ymin
        if other_speed == 0 and other_before:
            other_stops.append(frame)
        stopping_position = center if reference == 'nearest_surveyed_view' else front
        if speed == 0 and stopping_position <= point and ego_stop is None:
            ego_stop = frame
        if entry is None and front >= entry_point:
            entry = frame
            other_inside_at_entry = other_in
        if entry is not None and not other_in and other_clear_after_entry is None:
            other_clear_after_entry = frame
    if entry is None:
        raise ValueError('Ego entry absent from original history')
    prior_other_stop = min(other_stops) if other_stops else None
    # A stopped vehicle has precedence only if the stop was completed before
    # the ego's stop. This is an ordering fact, not a legal finding.
    prior_stop_precedence = (ego_stop is not None and prior_other_stop is not None
                             and prior_other_stop < ego_stop)
    return {
        'stop_reference': reference,
        'reference_x_m': point,
        'continuous_nearest_view_proven': False if reference == 'nearest_surveyed_view' else None,
        'ego_stop_frame': ego_stop,
        'ego_entry_frame': entry,
        'other_prior_stop_frame': prior_other_stop,
        'other_stopped_before_ego': prior_stop_precedence,
        'other_within_intersection_at_ego_entry': other_inside_at_entry,
        'other_clear_frame_at_or_after_ego_entry': other_clear_after_entry,
        'yield_judgment_proven': False,
        'cautious_proceeding_judgment_proven': False,
        'legal_verdict_claimed': False,
    }
