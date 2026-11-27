"""Measure a source-bound complete pedestrian crossing without a legal label."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from crosswalk_site import ASSIGNMENT, classify_body, point_in_polygon


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if (packet.get('assignment_id') != ASSIGNMENT or not packet.get('case_id') or
            not packet.get('original_trace_id') or
            type(packet.get('diagnostic_fixture')) is not bool):
        raise ValueError('original assignment, case and trace identity required')
    site = packet.get('site')
    if not isinstance(site, dict) or not site.get('roadway_id'):
        raise ValueError('original roadway source required')
    inventory = site.get('crosswalk_inventory')
    roadway = site.get('roadway_polygon_xy_m')
    if (not isinstance(inventory, dict) or not roadway or
            not site.get('start_curb_zone_polygon_xy_m') or
            not site.get('opposite_curb_zone_polygon_xy_m') or
            site.get('district_type') != 'business' or
            site.get('highway_span_ft') != 600 or
            not site.get('district_source_sha256') or
            not site.get('controls_source_sha256')):
        raise ValueError('original business-district, roadway and control context required')
    frames = packet.get('frames')
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError('three or more original pedestrian frames required')
    seen = set()
    states = []
    body_categories = []
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise ValueError('original pedestrian frame invalid')
        number, time_s = frame.get('frame'), frame.get('time_s')
        if (type(number) is not int or number in seen or
                type(time_s) not in (int, float) or not math.isfinite(time_s)):
            raise ValueError('finite unique original frame and time required')
        if index and (number <= frames[index - 1]['frame'] or
                      not 0 < time_s - frames[index - 1]['time_s'] <= 0.075):
            raise ValueError('ordered 20 Hz original frames required')
        seen.add(number)
        if (frame.get('observation_source') != ('synthetic_diagnostic' if packet['diagnostic_fixture']
                                               else 'original_native_snapshot') or
                frame.get('actor_id') != packet.get('pedestrian_actor_id')):
            raise ValueError('original pedestrian actor or snapshot source differs')
        body = frame.get('body_polygon_xy_m')
        if not isinstance(body, list) or len(body) < 3:
            raise ValueError('full original pedestrian body polygon required')
        on_road = any(point_in_polygon(vertex, roadway) for vertex in body)
        if frame.get('pedestrian_on_roadway') is not on_road:
            raise ValueError('roadway occupancy differs from original body polygon')
        if frame.get('curb_side') not in ('start', 'roadway', 'opposite'):
            raise ValueError('original curb-side history required')
        center = [sum(float(vertex[axis]) for vertex in body) / len(body)
                  for axis in (0, 1)]
        if frame['curb_side'] in ('start', 'opposite'):
            zone = site[frame['curb_side'] + '_curb_zone_polygon_xy_m']
            if not point_in_polygon(center, zone):
                raise ValueError('original pedestrian curb-side state differs from body position')
        states.append(frame['curb_side'])
        body_categories.append(classify_body(body, inventory))
    if (states[0] != 'start' or states[-1] != 'opposite' or
            'roadway' not in states or states.index('roadway') == 0 or
            states.index('roadway') == len(states) - 1):
        raise ValueError('complete start-to-opposite roadway crossing required')
    first_road = states.index('roadway')
    last_road = len(states) - 1 - states[::-1].index('roadway')
    if (any(state != 'roadway' for state in states[first_road:last_road + 1]) or
            any(state != 'start' for state in states[:first_road]) or
            any(state != 'opposite' for state in states[last_road + 1:])):
        raise ValueError('roadway crossing progression or opposite-curb exit differs')
    crossings = body_categories[first_road:last_road + 1]
    marked = [row['marked'] for row in crossings]
    unmarked = [row['unmarked'] for row in crossings]
    if any(a and b for a, b in zip(marked, unmarked)):
        raise ValueError('ambiguous overlapping marked and unmarked source geometry')
    return {
        'assignment_id': ASSIGNMENT,
        'case_id': packet['case_id'],
        'source': {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()},
        'original_trace_id': packet['original_trace_id'],
        'roadway_id': site['roadway_id'],
        'district_source_sha256': site['district_source_sha256'],
        'controls_source_sha256': site['controls_source_sha256'],
        'crossing_frame_bracket': [frames[first_road]['frame'], frames[last_road]['frame']],
        'complete_crossing_observed': True,
        'body_overlaps_marked_crosswalk_each_roadway_frame': all(marked),
        'body_overlaps_unmarked_crosswalk_each_roadway_frame': all(unmarked),
        'body_outside_both_each_roadway_frame': not any(marked) and not any(unmarked),
        'crosswalk_samples': crossings,
        'physical_and_legal_review': 'pending independent original-source and pixel audit',
    }
