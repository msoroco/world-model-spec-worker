"""Saved-source alley free-width diagnostic, without a legal judgment."""
from __future__ import annotations

import hashlib
import json
import math

ASSIGNMENT = 'training__C178965__NRS-484B-477-1b__motor_vehicle_driver'
RATE = 20
FRAMES = 600
TEN_FEET_M = 3.048


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def bounds(vehicle):
    x, y = vehicle['xy_m']
    yaw = vehicle['yaw_rad']
    half_l, half_w = vehicle['half_length_m'], vehicle['half_width_m']
    require(all(finite(v) for v in (x, y, yaw, half_l, half_w)) and half_l > 0 and half_w > 0,
            'invalid original vehicle footprint')
    cs, sn = math.cos(yaw), math.sin(yaw)
    corners = [(x + u * cs - v * sn, y + u * sn + v * cs)
               for u, v in ((half_l, half_w), (half_l, -half_w), (-half_l, -half_w), (-half_l, half_w))]
    return min(p[0] for p in corners), max(p[0] for p in corners), min(p[1] for p in corners), max(p[1] for p in corners)


def measure(packet_bytes: bytes, inventory_bytes: bytes):
    packet, inventory = json.loads(packet_bytes), json.loads(inventory_bytes)
    require(packet.get('assignment_id') == ASSIGNMENT == inventory.get('assignment_id'), 'assignment mismatch')
    kind = packet.get('source_kind')
    require(kind in ('synthetic_native_sample', 'native_saved_sample') and inventory.get('source_kind') == kind,
            'source kind mismatch')
    for field in ('public_highway_source_id', 'city_block_source_id', 'rear_access_source_id',
                  'abutting_property_source_id', 'non_culdesac_source_id',
                  'local_jurisdiction_source_id', 'local_ordinance_review_source_id'):
        require(inventory.get(field), field + ' missing')
    require(inventory.get('other_alley_scope_review_source_id'), 'other-alley scope source missing')
    y0, y1 = inventory.get('alley_lateral_edges_m', [None, None])
    require(finite(y0) and finite(y1) and y0 < y1, 'measured alley boundaries missing')
    require(inventory.get('boundary_measurement_source_id'), 'alley boundary measurement source missing')
    rows = packet.get('frames')
    require(isinstance(rows, list) and len(rows) == FRAMES, '600 original frames required')
    require([r.get('video_frame') for r in rows] == list(range(FRAMES)), 'missing or unordered video frames')
    require(all(finite(r.get('native_frame')) for r in rows) and
            all(rows[i]['native_frame'] < rows[i+1]['native_frame'] for i in range(FRAMES-1)),
            'nonmonotonic Native frame identity')
    require(all(finite(r.get('time_s')) and abs(r['time_s'] - i / RATE) < .005 for i, r in enumerate(rows)),
            'missing original 20 Hz timing')
    require(packet.get('subject_id') and packet.get('other_id') and packet['subject_id'] != packet['other_id'],
            'distinct vehicle identities missing')
    widths = []
    halt_frames = []
    for i, row in enumerate(rows):
        subject, other = row['subject'], row['other']
        require(subject.get('vehicle_id') == packet['subject_id'] and other.get('vehicle_id') == packet['other_id'],
                'vehicle identity changed')
        require(finite(subject.get('speed_mps')) and subject['speed_mps'] >= 0,
                'invalid original subject speed')
        sx0, sx1, sy0, sy1 = bounds(subject)
        ox0, ox1, oy0, oy1 = bounds(other)
        require(y0 <= sy0 <= sy1 <= y1 and y0 <= oy0 <= oy1 <= y1,
                'vehicle footprint outside measured alley')
        if subject['speed_mps'] <= .1:
            halt_frames.append(i)
        if min(sx1, ox1) < max(sx0, ox0):
            widths.append(None)
        else:
            widths.append(max(0.0, max(sy0, oy0) - min(sy1, oy1)) if (sy1 < oy0 or oy1 < sy0) else 0.0)
    measured_halt = [widths[i] for i in halt_frames if widths[i] is not None]
    return {'format': 'c178965-saved-alley-width-diagnostic-v1',
            'assignment_id': ASSIGNMENT, 'source_kind': kind,
            'packet_sha256': hashlib.sha256(packet_bytes).hexdigest(),
            'inventory_sha256': hashlib.sha256(inventory_bytes).hexdigest(),
            'frame_count': FRAMES, 'duration_s': FRAMES / RATE,
            'alley_lateral_edges_m': [y0, y1], 'alley_width_m': y1 - y0,
            'subject_halt_proxy_frames': halt_frames,
            'cross_section_free_width_m_by_frame': widths,
            'minimum_measured_halt_free_width_m': min(measured_halt) if measured_halt else None,
            'measured_halt_frames_below_10_feet': [i for i in halt_frames if widths[i] is not None and widths[i] < TEN_FEET_M],
            'statutory_10_feet_m': TEN_FEET_M,
            'legal_result': None,
            'unresolved': ['local ordinance legal effect', 'other-alley antecedent',
                           'alley definition and public access', 'stopping, standing, parking purpose',
                           'free movement of vehicular traffic', 'original Native physical review']}
