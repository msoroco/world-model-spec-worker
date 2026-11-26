"""Measure full-body divided-road crossing from saved frame sources.

The measurement reports geometry and motion. Public authority and statutory
judgment remain separate original-source review questions.
"""
import hashlib
import json
import math
from pathlib import Path

from median_scene import BARRIER_BOUNDS, CAMERAS, MEDIAN_BOUNDS, OPENING_BOUNDS
from native.measure_median import overlap_area


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing required source: '+path.name)
    result = [json.loads(line) for line in path.read_text().splitlines()]
    if len(result) != 600:
        raise ValueError('Incomplete 600-frame source: '+path.name)
    return result


def measure_attempt(attempt):
    attempt = Path(attempt)
    context_path = attempt/'median-context.json'
    if not context_path.is_file():
        raise ValueError('Missing required source: median-context.json')
    context = json.loads(context_path.read_text())
    if context.get('source_kind') not in ('synthetic_native_sample',
                                          'original_native_median_readback'):
        raise ValueError('Median source provenance missing')
    if context.get('median_bounds_m') != MEDIAN_BOUNDS or context.get('opening_bounds_m') != OPENING_BOUNDS or context.get('barrier_bounds_m') != BARRIER_BOUNDS:
        raise ValueError('Median geometry differs from selected scene')
    review_sha = None
    if context['source_kind'] == 'original_native_median_readback':
        review_path = attempt/'source-review.json'
        if not review_path.is_file():
            raise ValueError('Original median source review missing')
        review = json.loads(review_path.read_text())
        bound = review.get('source_sha256', {})
        needed = {'road.xodr', 'median-context.json', 'native-median.jsonl',
                  'video_frames.jsonl', 'capture-seal.json',
                  *(name+'.mkv' for name, _, _ in CAMERAS)}
        if review.get('format') != 'worker-original-median-source-review' or not needed <= set(bound):
            raise ValueError('Original median source review incomplete')
        if any(not (attempt/name).is_file() or sha(attempt/name) != digest
               for name, digest in bound.items()):
            raise ValueError('Original median source hash differs')
        topics = review.get('confirmed_topics', {})
        for topic in ('two_directional_roadways', 'median_and_opening_geometry',
                      'full_vehicle_footprint', 'turn_and_crossing_history',
                      'four_camera_visibility'):
            item = topics.get(topic, {})
            if item.get('confirmed') is not True or not item.get('source_refs') or not set(item['source_refs']) <= set(bound):
                raise ValueError('Original median topic review missing: '+topic)
        review_sha = sha(review_path)
    motion = rows(attempt/'native-median.jsonl')
    frames = rows(attempt/'video_frames.jsonl')
    counts = {'median': 0, 'opening': 0, 'barrier': 0,
              'right_hand_roadway': 0, 'opposite_roadway': 0}
    maximum = {'median_m2': 0.0, 'opening_m2': 0.0, 'barrier_m2': 0.0}
    crossing_frames = []
    preceding = None
    camera_names = {name for name, _, _ in CAMERAS}
    for index, (row, frame) in enumerate(zip(motion, frames)):
        native = row.get('native_frame')
        if type(native) is not int or (preceding is not None and native <= preceding):
            raise ValueError('Native frame identity differs')
        preceding = native
        if row.get('video_frame') != index or frame.get('video_frame') != index or frame.get('native_frame') != native or frame.get('camera_native_frames') != {name: native for name in camera_names}:
            raise ValueError('Four-camera native frame join differs')
        if abs(float(row.get('time_s', -1)) - index/20) > 1e-6:
            raise ValueError('20 Hz source time differs')
        ego = row.get('ego', {})
        body = ego.get('body_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Full-body source footprint missing')
        speed = ego.get('speed_mps')
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Original speed missing')
        median = overlap_area(body, MEDIAN_BOUNDS)
        opening = overlap_area(body, OPENING_BOUNDS)
        barrier = sum(overlap_area(body, bounds) for bounds in BARRIER_BOUNDS)
        if abs(median-opening-barrier) > 1e-6:
            raise ValueError('Median partition differs')
        if median > 1e-6:
            counts['median'] += 1
            crossing_frames.append(index)
            if speed <= 0:
                raise ValueError('Stopped body cannot prove driven crossing')
        if opening > 1e-6:
            counts['opening'] += 1
        if barrier > 1e-6:
            counts['barrier'] += 1
        if any(point[1] < -2 for point in body):
            counts['right_hand_roadway'] += 1
        if any(point[1] > 2 for point in body):
            counts['opposite_roadway'] += 1
        for name, value in (('median_m2', median), ('opening_m2', opening),
                            ('barrier_m2', barrier)):
            maximum[name] = max(maximum[name], value)
    if not crossing_frames:
        raise ValueError('No observed median crossing')
    return {'format': 'worker-source-median-turn-measurement',
            'frame_count': 600, 'rate_hz': 20, 'occupancy_frames': counts,
            'first_crossing_frame': crossing_frames[0],
            'last_crossing_frame': crossing_frames[-1],
            'max_overlap_m2': maximum, 'source_review_sha256': review_sha,
            'diagnostic_fixture': review_sha is None,
            'public_authority_establishment': 'unassessed',
            'physical_acceptance_claimed': False, 'legal_compliance': 'unassessed',
            'source_sha256': {name: sha(attempt/name) for name in
                              ('median-context.json', 'native-median.jsonl',
                               'video_frames.jsonl')}}
