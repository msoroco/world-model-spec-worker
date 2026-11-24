"""Source-bound officer direction exception measurement; no legal verdict."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def measure(root):
    root = Path(root)
    names = ('video_frames.jsonl', 'vehicle_poses.jsonl',
             'officer_track.jsonl', 'officer_direction.json')
    if any(not (root / name).is_file() for name in names):
        raise ValueError('Original frame, pose, officer track and direction review required')
    frames, poses, track = (rows(root / name) for name in names[:3])
    review = json.loads((root / names[3]).read_text())
    if len(frames) != 600 or len(poses) != 600 or len(track) != 600:
        raise ValueError('Full 600-frame officer source join required')
    if review.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Officer source provenance required')
    for field in ('reviewer', 'law_enforcement_identity_source',
                  'direction_visual_source', 'direction_to_subject_source'):
        if not review.get(field):
            raise ValueError('Officer identity or visible direction source missing: ' + field)
    if review.get('directed_otherwise') is not True or review.get('directive') != 'continue_travel':
        raise ValueError('Exact otherwise-directed response is unreviewed')
    if type(review.get('officer_actor_id')) is not int or type(review.get('ego_actor_id')) is not int:
        raise ValueError('Distinct officer and driver actor IDs required')
    if review['officer_actor_id'] == review['ego_actor_id']:
        raise ValueError('Officer and driver actor identities overlap')
    for name in names[:3]:
        if review.get('source_sha256', {}).get(name) != sha(root / name):
            raise ValueError('Officer source hash differs: ' + name)
    if review['review_kind'] == 'original_source_review':
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            name = camera + '.mkv'
            if not (root / name).is_file() or review.get('camera_sha256', {}).get(name) != sha(root / name):
                raise ValueError('Original officer camera source missing or changed: ' + name)
    observed = []
    previous_native = -1
    previous_time = -1.0
    for index, (frame, pose, officer) in enumerate(zip(frames, poses, track)):
        native, time = frame.get('native_frame'), frame.get('time_s')
        if (frame.get('video_frame') != index or pose.get('video_frame') != index or
                officer.get('video_frame') != index or type(native) is not int or
                native <= previous_native or pose.get('native_frame') != native or
                officer.get('native_frame') != native or type(time) not in (int, float) or
                not math.isfinite(time) or time <= previous_time or
                (index and abs(time - previous_time - .05) > .005)):
            raise ValueError('Original officer/frame/pose time join differs')
        ego = pose.get('ego', {})
        if ego.get('actor_id') != review['ego_actor_id'] or officer.get('actor_id') != review['officer_actor_id']:
            raise ValueError('Officer or driver identity differs')
        for field in ('x_m', 'y_m'):
            if (type(officer.get(field)) not in (int, float) or not math.isfinite(officer[field]) or
                    type(ego.get(field)) not in (int, float) or not math.isfinite(ego[field])):
                raise ValueError('Officer or driver position missing')
        if math.hypot(officer['x_m'] - ego['x_m'], officer['y_m'] - ego['y_m']) > 80:
            raise ValueError('Officer is outside requested driver scene')
        if type(officer.get('direction_active')) is not bool:
            raise ValueError('Original officer direction state missing')
        if officer['direction_active']:
            observed.append(index)
        previous_native, previous_time = native, time
    if not observed or min(observed) > 120 or max(observed) < 180:
        raise ValueError('Officer direction interval is not present during approach')
    return {'case_id': review['case_id'], 'directive': review['directive'],
            'direction_start_frame': min(observed), 'direction_end_frame': max(observed),
            'source_sha256': {name: sha(root / name) for name in names},
            'visual_direction_verified': False,
            'original_review_declared': review['review_kind'] == 'original_source_review',
            'legal_verdict': None, 'physical_acceptance_claimed': False}
