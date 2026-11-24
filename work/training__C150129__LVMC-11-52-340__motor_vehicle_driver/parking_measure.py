"""Source-bound parking footprint diagnostic; never a municipal legal verdict."""
from __future__ import annotations

import hashlib
import json
import math

ASSIGNMENT = 'training__C150129__LVMC-11-52-340__motor_vehicle_driver'
RATE = 20
FRAMES = 600


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _inside(point, polygon):
    x, y = point
    result = False
    for i, (ax, ay) in enumerate(polygon):
        bx, by = polygon[i - 1]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            result = not result
    return result


def _corners(row):
    x, y = row['vehicle_xy_m']
    yaw = row['yaw_rad']
    half_l, half_w = row['bbox_half_length_m'], row['bbox_half_width_m']
    require(all(_finite(v) for v in (x, y, yaw, half_l, half_w)) and half_l > 0 and half_w > 0,
            'invalid original vehicle footprint')
    cs, sn = math.cos(yaw), math.sin(yaw)
    return [[x + u * cs - v * sn, y + u * sn + v * cs]
            for u, v in ((half_l, half_w), (half_l, -half_w), (-half_l, -half_w), (-half_l, half_w))]


def measure(packet_bytes: bytes, inventory_bytes: bytes):
    packet, inventory = json.loads(packet_bytes), json.loads(inventory_bytes)
    require(packet.get('assignment_id') == ASSIGNMENT == inventory.get('assignment_id'), 'assignment mismatch')
    kind = packet.get('source_kind')
    require(kind in ('synthetic_native_sample', 'native_saved_sample') and inventory.get('source_kind') == kind,
            'source kind mismatch')
    require(inventory.get('city_street_source_id'), 'City-street jurisdiction source missing')
    require(inventory.get('council_designation_source_id'), 'City Council designation source missing')
    require(inventory.get('space_id') and inventory.get('posting_or_marking_source_id'),
            'space posting or marking source missing')
    require(inventory.get('posting_space_id') == inventory['space_id'], 'posting-space association missing')
    require(inventory.get('subject_status_source_id'), 'subject City-vehicle status source missing')
    require(inventory.get('subject_city_vehicle') is False, 'non-City vehicle source missing')
    polygon = inventory.get('space_polygon_xy_m')
    require(isinstance(polygon, list) and len(polygon) >= 3 and
            all(isinstance(p, list) and len(p) == 2 and all(_finite(v) for v in p) for p in polygon),
            'space boundary source missing')
    rows = packet.get('frames')
    require(isinstance(rows, list) and len(rows) == FRAMES, '600 original frames required')
    require([r.get('video_frame') for r in rows] == list(range(FRAMES)), 'missing or unordered video frames')
    require(all(_finite(r.get('native_frame')) for r in rows) and
            all(rows[i]['native_frame'] < rows[i + 1]['native_frame'] for i in range(FRAMES - 1)),
            'nonmonotonic Native frame identity')
    require(all(_finite(r.get('time_s')) and abs(r['time_s'] - i / RATE) < .005 for i, r in enumerate(rows)),
            'missing original 20 Hz timing')
    require(packet.get('vehicle_id') and all(r.get('vehicle_id') == packet['vehicle_id'] for r in rows),
            'subject vehicle identity changed')
    require(all(_finite(r.get('speed_mps')) and r['speed_mps'] >= 0 for r in rows),
            'invalid original speed')
    occupied = [i for i, r in enumerate(rows) if all(_inside(p, polygon) for p in _corners(r))]
    parked_motion_proxy = [i for i, r in enumerate(rows) if r['speed_mps'] <= .1]
    both = sorted(set(occupied) & set(parked_motion_proxy))
    return {
        'format': 'c150129-saved-city-parking-diagnostic-v1',
        'assignment_id': ASSIGNMENT, 'source_kind': kind,
        'packet_sha256': hashlib.sha256(packet_bytes).hexdigest(),
        'inventory_sha256': hashlib.sha256(inventory_bytes).hexdigest(),
        'frame_count': FRAMES, 'duration_s': FRAMES / RATE,
        'space_id': inventory['space_id'],
        'city_street_source_id': inventory['city_street_source_id'],
        'council_designation_source_id': inventory['council_designation_source_id'],
        'posting_or_marking_source_id': inventory['posting_or_marking_source_id'],
        'subject_status_source_id': inventory['subject_status_source_id'],
        'occupied_frames': occupied,
        'stationary_proxy_frames': parked_motion_proxy,
        'occupied_and_stationary_proxy_frames': both,
        'legal_result': None,
        'unresolved': ['independent designation and due-posting review',
                       'independent City-vehicle classification', 'parking purpose and loading activity',
                       'original Native and video pixel review'],
    }
