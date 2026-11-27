"""Original-frame lamp and parking facts for NRS 484B.473(2).

A Native light request or weather setting cannot establish optical dimming,
nighttime, public-highway status, or lawful parking. Those are independent
source-review findings joined to the original capture here.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = 'training__C229422__NRS-484B-473-2__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _rows(raw):
    return [json.loads(row) for row in raw.splitlines() if row.strip()]


def measure(trace_raw, map_raw, review_raw, camera_hashes):
    trace, mapping = _rows(trace_raw), _rows(map_raw)
    review = json.loads(review_raw)
    require(len(trace) == len(mapping) == FRAMES, 'Full 600-frame original parked interval required')
    require(review.get('assignment_id') == ASSIGNMENT and
            review.get('source_kind') in ('independent_original_review', 'synthetic_diagnostic') and
            review.get('trace_sha256') == sha(trace_raw) and
            review.get('frame_map_sha256') == sha(map_raw) and
            review.get('camera_sha256') == camera_hashes,
            'Source-bound independent lamp review missing or stale')
    require(review.get('reviewer_id') and review.get('lawful_parking_source') and
            review.get('civil_night_source') and review.get('highway_source'),
            'Original lawful parking, highway and civil-night provenance required')
    require(type(review.get('lawfully_parked')) is bool and
            type(review.get('highway')) is bool and
            type(review.get('civil_night')) is bool,
            'Independent activation findings required')
    observations = review.get('optical_observations')
    require(isinstance(observations, list) and len(observations) == FRAMES,
            'Every displayed-lamp frame needs original optical review')
    counts = {'displayed': 0, 'depressed_or_dimmed': 0,
              'undepressed': 0, 'cowl_or_parking': 0}
    first_native = trace[0].get('native_frame')
    first_elapsed = trace[0].get('native_elapsed_s')
    require(type(first_native) is int and type(first_elapsed) in (int, float),
            'Original Native time origin missing')
    for i, (actor, frame, optical) in enumerate(zip(trace, mapping, observations)):
        require(actor.get('video_frame') == frame.get('video_frame') == optical.get('video_frame') == i and
                actor.get('native_frame') == frame.get('native_frame') == first_native+i and
                abs(actor.get('native_elapsed_s', -1)-frame.get('native_elapsed_s', -2)) < 1e-5 and
                abs(actor['native_elapsed_s']-first_elapsed-i/20) < 1e-4,
                'Original Native/frame/time join differs')
        speed = actor.get('ego_speed_mps')
        require(type(speed) in (int, float) and math.isfinite(speed) and speed <= 0.1,
                'Vehicle did not remain stopped for parked interval')
        require(actor.get('vehicle_actor_id') and actor.get('road_id') and
                type(actor.get('headlamp_request')) is str,
                'Original vehicle, road or lamp request trace missing')
        require(optical.get('source_camera') in CAMERAS and
                isinstance(optical.get('pixel_box_xyxy'), list) and
                len(optical['pixel_box_xyxy']) == 4,
                'Original optical pixel location missing')
        values = [optical.get(k) for k in ('lights_displayed', 'depressed_or_dimmed',
                                          'undepressed_headlamp', 'cowl_or_parking_used')]
        require(all(type(v) is bool for v in values),
                'Independent optical lamp findings missing')
        displayed, dimmed, full, parking = values
        require(not (dimmed and full) and (displayed or not (dimmed or full or parking)),
                'Contradictory optical lamp findings')
        counts['displayed'] += displayed
        counts['depressed_or_dimmed'] += dimmed
        counts['undepressed'] += full
        counts['cowl_or_parking'] += parking
    return {'format': 'c229422-original-lamp-measurement-v1',
            'assignment_id': ASSIGNMENT, 'frame_count': FRAMES, 'duration_s': 30,
            'source_kind': review['source_kind'], 'activation': {
                'lawfully_parked': review['lawfully_parked'],
                'highway': review['highway'], 'civil_night': review['civil_night']},
            'optical_frame_counts': counts, 'trace_sha256': sha(trace_raw),
            'frame_map_sha256': sha(map_raw), 'review_sha256': sha(review_raw),
            'camera_sha256': camera_hashes, 'legal_conclusion': None,
            'native_light_request_is_optical_evidence': False}


def measure_files(root):
    root = Path(root)
    sources = ['parked-lamp-trace.jsonl', 'video_frames.jsonl', 'lamp-pixel-review.json']
    for name in sources:
        require((root/name).is_file(), 'Missing required original source: '+name)
    hashes = {}
    for camera in CAMERAS:
        path = root/(camera+'.mkv')
        require(path.is_file(), 'Missing original camera source: '+camera)
        hashes[camera] = sha(path.read_bytes())
    return measure((root/sources[0]).read_bytes(), (root/sources[1]).read_bytes(),
                   (root/sources[2]).read_bytes(), hashes)
