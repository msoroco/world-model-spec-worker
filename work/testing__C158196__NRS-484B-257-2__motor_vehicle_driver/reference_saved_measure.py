"""Measure authored stopping-reference placement from full Native sources."""

import json
import hashlib
import math
from pathlib import Path

from stopping_reference import from_authored_site
from officer_direction import REFERENCE_SUFFIXES, behavior_suffix


FRAMES = 600


def measure(capture_path, site_path):
    capture = json.loads(Path(capture_path).read_text())
    reference = from_authored_site(site_path)
    suffix = behavior_suffix(capture.get('case_id'))
    expected_kind = {'stop_line_reference': 'stop_line',
                     'crosswalk_reference': 'near_crosswalk',
                     'nearest_view_reference': 'nearest_view'}
    if suffix in REFERENCE_SUFFIXES and reference['kind'] != expected_kind[suffix]:
        raise ValueError('Exact reference case and authored site differ')
    site_sha = hashlib.sha256(Path(site_path).read_bytes()).hexdigest()
    if (capture.get('format') != 'worker-subsection-2-officer-native-capture' or
            capture.get('frame_count') != FRAMES or
            capture.get('fixed_delta_seconds') != 0.05 or
            capture.get('site_sha256') != site_sha or
            not isinstance(capture.get('rows'), list) or
            len(capture['rows']) != FRAMES):
        raise ValueError('Complete original 20 Hz Native capture required')
    rows = capture['rows']
    stopped = []
    overshot_before_stop = False
    prior_frame = -1
    prior_time = None
    for index, row in enumerate(rows):
        frame = row.get('carla_frame')
        time_s = row.get('time_s')
        if (row.get('frame_index') != index or type(frame) is not int or
                frame <= prior_frame or type(time_s) not in (int, float) or
                not math.isfinite(time_s) or
                (prior_time is not None and abs(time_s - prior_time - 0.05) > 1e-4)):
            raise ValueError('Original stopping-reference frame join differs')
        prior_frame, prior_time = frame, time_s
        if row.get('stopping_reference') != reference:
            raise ValueError('Original stopping reference differs from authored site')
        body = row.get('ego_body_vertices_xy_m')
        if (not isinstance(body, list) or len(body) != 8 or
                any(not isinstance(point, list) or len(point) != 2 or
                    any(type(v) not in (int, float) or not math.isfinite(v)
                        for v in point) for point in body)):
            raise ValueError('Complete original ego body missing')
        front_x = max(point[0] for point in body)
        speed = row.get('ego_speed_mps')
        if (type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0 or
                row.get('ego_front_x_m') != front_x):
            raise ValueError('Original ego body or speed readback differs')
        if not stopped and front_x > reference['x_m']:
            overshot_before_stop = True
        if speed <= 0.05 and front_x <= reference['x_m']:
            stopped.append({'frame_index': index, 'carla_frame': frame,
                            'time_s': float(time_s), 'ego_front_x_m': front_x,
                            'ego_speed_mps': float(speed)})
    return {'case_id': capture['case_id'], 'reference_kind': reference['kind'],
            'reference_source': reference['source'],
            'reference_x_m': reference['x_m'],
            'original_frame_count': FRAMES,
            'first_engineering_stop_before_reference': stopped[0] if stopped else None,
            'engineering_stop_sample_count': len(stopped),
            'overshot_before_engineering_stop': overshot_before_stop,
            'legal_stop_judgment': 'unresolved',
            'visibility_judgment': 'unreviewed' if reference['legal_visibility_review_pending']
                                   else 'not_applicable'}
