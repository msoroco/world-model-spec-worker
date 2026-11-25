"""Saved-source crosswalk distance diagnostics; no legal distance convention chosen."""
from __future__ import annotations

import hashlib
import json
import math

ASSIGNMENT = 'training__C229397__LVMC-11-52-130-A12__motor_vehicle_driver'
FRAMES = 600
RATE = 20
TWENTY_FEET_M = 6.096


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def body_corners(row):
    x, y = row['vehicle_xy_m']
    yaw, length, width = row['yaw_rad'], row['bbox_half_length_m'], row['bbox_half_width_m']
    require(all(finite(v) for v in (x, y, yaw, length, width)) and length > 0 and width > 0,
            'invalid original vehicle body')
    cs, sn = math.cos(yaw), math.sin(yaw)
    return [(x + u * cs - v * sn, y + u * sn + v * cs)
            for u, v in ((length, width), (length, -width), (-length, -width), (-length, width))]


def point_rect_distance(p, rect):
    x0, x1, y0, y1 = rect
    return math.hypot(max(x0 - p[0], 0, p[0] - x1), max(y0 - p[1], 0, p[1] - y1))


def point_segment_distance(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / (vx * vx + vy * vy)))
    return math.dist(p, (a[0] + t * vx, a[1] + t * vy))


def body_rect_distance(corners, rect):
    x0, x1, y0, y1 = rect
    rectangle = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    # A rectangle corner can lie inside the vehicle while every edge and
    # vehicle corner remains away from the crosswalk boundary.
    def orientation(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def intersects(a, b, c, d):
        if (max(min(a[0], b[0]), min(c[0], d[0])) > min(max(a[0], b[0]), max(c[0], d[0])) or
                max(min(a[1], b[1]), min(c[1], d[1])) > min(max(a[1], b[1]), max(c[1], d[1]))):
            return False
        o1, o2 = orientation(a, b, c), orientation(a, b, d)
        o3, o4 = orientation(c, d, a), orientation(c, d, b)
        return o1 * o2 <= 0 and o3 * o4 <= 0

    def in_body(p):
        turns = [orientation(corners[i], corners[(i + 1) % 4], p) for i in range(4)]
        return all(t >= -1e-9 for t in turns) or all(t <= 1e-9 for t in turns)

    if any(in_body(p) for p in rectangle) or any(point_rect_distance(p, rect) == 0 for p in corners):
        return 0.0
    if any(intersects(corners[i], corners[(i + 1) % 4],
                      rectangle[j], rectangle[(j + 1) % 4])
           for i in range(4) for j in range(4)):
        return 0.0
    values = [point_rect_distance(p, rect) for p in corners]
    for p in rectangle:
        values.extend(point_segment_distance(p, corners[i], corners[(i + 1) % 4]) for i in range(4))
    return min(values)


def measure(packet_bytes: bytes, inventory_bytes: bytes):
    packet, inventory = json.loads(packet_bytes), json.loads(inventory_bytes)
    require(packet.get('assignment_id') == ASSIGNMENT == inventory.get('assignment_id'), 'assignment mismatch')
    kind = packet.get('source_kind')
    require(kind in ('synthetic_native_sample', 'native_saved_sample') and inventory.get('source_kind') == kind,
            'source kind mismatch')
    for key in ('jurisdiction_source_id', 'marked_crosswalk_source_id', 'crosswalk_extent_source_id',
                'responsible_person_source_id', 'traffic_conflict_review_source_id',
                'law_compliance_review_source_id', 'directions_review_source_id'):
        require(inventory.get(key), key + ' missing')
    rect = inventory.get('crosswalk_rect_xyxy_m')
    require(isinstance(rect, list) and len(rect) == 4 and all(finite(v) for v in rect)
            and rect[0] < rect[1] and rect[2] < rect[3], 'marked crosswalk extent missing')
    rows = packet.get('frames')
    require(isinstance(rows, list) and len(rows) == FRAMES, '600 original frames required')
    require([r.get('video_frame') for r in rows] == list(range(FRAMES)), 'missing or unordered video frames')
    require(all(finite(r.get('native_frame')) for r in rows) and
            all(rows[i]['native_frame'] < rows[i+1]['native_frame'] for i in range(FRAMES-1)),
            'nonmonotonic Native frame identity')
    require(all(finite(r.get('time_s')) and abs(r['time_s'] - i / RATE) < .005 for i, r in enumerate(rows)),
            'missing original 20 Hz timing')
    require(packet.get('vehicle_id') and all(r.get('vehicle_id') == packet['vehicle_id'] for r in rows),
            'subject identity changed')
    require(all(finite(r.get('speed_mps')) and r['speed_mps'] >= 0 for r in rows),
            'invalid original subject speed')
    centers = [point_rect_distance(r['vehicle_xy_m'], rect) for r in rows]
    bodies = [body_rect_distance(body_corners(r), rect) for r in rows]
    along = [rect[0] - max(p[0] for p in body_corners(r)) for r in rows]
    halt = [i for i, r in enumerate(rows) if r['speed_mps'] <= .1]
    halt_set = set(halt)
    spans = []
    start = None
    for i in range(FRAMES + 1):
        if i in halt_set and start is None:
            start = i
        elif i not in halt_set and start is not None:
            spans.append({'first_frame': start, 'last_frame_inclusive': i - 1,
                          'sampled_duration_s': (i - start) / RATE,
                          'minimum_body_distance_m': min(bodies[start:i]),
                          'maximum_body_distance_m': max(bodies[start:i])})
            start = None
    return {'format': 'c229397-saved-crosswalk-distance-diagnostic-v1',
            'assignment_id': ASSIGNMENT, 'source_kind': kind,
            'packet_sha256': hashlib.sha256(packet_bytes).hexdigest(),
            'inventory_sha256': hashlib.sha256(inventory_bytes).hexdigest(),
            'frame_count': FRAMES, 'duration_s': FRAMES / RATE,
            'marked_crosswalk_source_id': inventory['marked_crosswalk_source_id'],
            'crosswalk_extent_source_id': inventory['crosswalk_extent_source_id'],
            'crosswalk_rect_xyxy_m': rect,
            'halt_proxy_frames': halt,
            'halt_proxy_spans': spans,
            'center_to_crosswalk_m_by_frame': centers,
            'body_to_crosswalk_m_by_frame': bodies,
            'along_road_body_gap_m_by_frame': along,
            'halt_body_distance_below_20ft_frames': [i for i in halt if bodies[i] < TWENTY_FEET_M],
            'halt_center_distance_below_20ft_frames': [i for i in halt if centers[i] < TWENTY_FEET_M],
            'statutory_20_feet_m': TWENTY_FEET_M,
            'legal_result': None,
            'unresolved': ['statutory measurement convention and boundary meaning',
                           'whether crosswalk is actually marked', 'traffic-conflict exception',
                           'law, police and device direction exceptions', 'parking purpose',
                           'original Native and video pixel review']}
