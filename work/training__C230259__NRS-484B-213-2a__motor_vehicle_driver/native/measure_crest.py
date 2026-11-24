"""Source-bound geometry diagnostic for NRS 484B.213(2)(a).

No numerical sight distance is a legal hazard threshold. This module reports
raw sight brackets and time alignment for independent original-source review.
"""
import hashlib
import json
from pathlib import Path

RATE = 20
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(trace_path, road_path):
    road = json.loads(Path(road_path).read_text())
    trace = rows(trace_path)
    if len(trace) != FRAMES or [r.get('frame') for r in trace] != list(range(FRAMES)):
        raise ValueError('missing or disordered 600-frame original source trace')
    if road.get('directionality') not in ('two_way', 'one_way') or road.get('center_y_m') is None:
        raise ValueError('missing source road directionality or centerline')
    if road.get('crest_x_m') is None or road.get('grade_profile_source') is None:
        raise ValueError('missing source grade and crest geometry')
    center = float(road['center_y_m'])
    crest = float(road['crest_x_m'])
    left_frames = []
    approach_frames = []
    sight = []
    oncoming = []
    for r in trace:
        if r.get('ego_id') is None or r.get('ego_bbox_y_min_m') is None or r.get('ego_bbox_y_max_m') is None:
            raise ValueError('missing source ego identity or footprint')
        if r.get('ego_x_m') is None or r.get('sight_clear_m') is None or r.get('sight_censored') is None:
            raise ValueError('missing source position or sightline bracket')
        if r.get('camera_frame_ids') is None or set(r['camera_frame_ids']) != {'overview','approach','reference_corner','driver_reference'}:
            raise ValueError('missing four-camera frame identity')
        if any(v != r['frame'] for v in r['camera_frame_ids'].values()):
            raise ValueError('camera/source frame misjoin')
        if float(r['ego_bbox_y_min_m']) < center:
            left_frames.append(r['frame'])
        if float(r['ego_x_m']) < crest and float(r.get('ego_forward_mps', 0)) > 0:
            approach_frames.append(r['frame'])
        sight.append({'frame': r['frame'], 'clear_m': float(r['sight_clear_m']),
                      'censored': bool(r['sight_censored'])})
        if r.get('other_vehicle_id') is not None:
            if r.get('other_vehicle_direction') is None or r.get('other_vehicle_x_m') is None:
                raise ValueError('missing other vehicle direction or position')
            if r['other_vehicle_direction'] == 'opposing':
                oncoming.append(r['frame'])
    approach = set(approach_frames)
    overlap = sorted(approach.intersection(left_frames))
    return {
        'format': 'worker-crest-source-measurement-v1', 'frames': FRAMES, 'rate_hz': RATE,
        'trace_sha256': sha(trace_path), 'road_sha256': sha(road_path),
        'road_directionality': road['directionality'], 'one_way_exception_observed': road['directionality'] == 'one_way',
        'crest_x_m': crest, 'center_y_m': center, 'grade_profile_source': road['grade_profile_source'],
        'approach_first_frame': min(approach_frames) if approach_frames else None,
        'approach_last_frame': max(approach_frames) if approach_frames else None,
        'left_of_center_first_frame': min(left_frames) if left_frames else None,
        'left_of_center_last_frame': max(left_frames) if left_frames else None,
        'approach_left_overlap_first_frame': min(overlap) if overlap else None,
        'approach_left_overlap_count': len(overlap),
        'sight_clear_min_m': min(v['clear_m'] for v in sight),
        'sight_clear_max_m': max(v['clear_m'] for v in sight),
        'sight_censored_frames': sum(v['censored'] for v in sight),
        'sight_clear_min_during_approach_left_m': min((sight[i]['clear_m'] for i in overlap), default=None),
        'uncensored_sight_frames_during_approach_left': sum(not sight[i]['censored'] for i in overlap),
        'opposing_vehicle_observed_frames': len(oncoming),
        'hazard_distance_legal_judgment': None, 'physical_completion': None,
    }
