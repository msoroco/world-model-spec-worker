"""Source-bound hand-signal preparation indicator; no legal or visibility verdict."""
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
             'driver_hand_track.jsonl', 'hand_signal_review.json')
    if any(not (root / name).is_file() for name in names):
        raise ValueError('Frame, pose, driver hand track and signal review required')
    frames, poses, track = (rows(root / name) for name in names[:3])
    review = json.loads((root / names[3]).read_text())
    if len(frames) != 600 or len(poses) != 600 or len(track) != 600:
        raise ValueError('Full 600-frame driver hand source join required')
    if review.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Driver hand source provenance required')
    for key in ('reviewer', 'driver_identity_source', 'hand_signal_visual_source',
                'signal_to_subject_source'):
        if not review.get(key):
            raise ValueError('Driver hand source review missing: ' + key)
    if review.get('preparing_to_move') is not True:
        raise ValueError('Preparation by hand signal not reviewed')
    ids = (review.get('ego_actor_id'), review.get('source_vehicle_actor_id'),
           review.get('source_driver_actor_id'))
    if any(type(value) is not int for value in ids) or len(set(ids)) != 3:
        raise ValueError('Distinct ego, source vehicle and driver actor IDs required')
    for name in names[:3]:
        if review.get('source_sha256', {}).get(name) != sha(root / name):
            raise ValueError('Driver hand source hash differs: ' + name)
    if review['review_kind'] == 'original_source_review':
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            name = camera + '.mkv'
            if not (root / name).is_file() or review.get('camera_sha256', {}).get(name) != sha(root / name):
                raise ValueError('Original hand-signal camera missing or changed: ' + name)
    active = []
    previous_native = -1
    previous_time = -1.0
    for index, (frame, pose, hand) in enumerate(zip(frames, poses, track)):
        native, time = frame.get('native_frame'), frame.get('time_s')
        if (frame.get('video_frame') != index or pose.get('video_frame') != index or
                hand.get('video_frame') != index or type(native) is not int or
                native <= previous_native or pose.get('native_frame') != native or
                hand.get('native_frame') != native or type(time) not in (int, float) or
                not math.isfinite(time) or time <= previous_time or
                (index and abs(time - previous_time - .05) > .005)):
            raise ValueError('Driver hand/frame/pose time join differs')
        ego, source = pose.get('ego', {}), pose.get('emergency', {})
        if (ego.get('actor_id') != ids[0] or source.get('actor_id') != ids[1] or
                hand.get('actor_id') != ids[2] or hand.get('source_vehicle_actor_id') != ids[1]):
            raise ValueError('Driver hand actor or source vehicle identity differs')
        if type(hand.get('signal_active')) is not bool:
            raise ValueError('Driver hand signal state missing')
        if hand['signal_active']:
            bones = hand.get('pose_bones_requested')
            if not isinstance(bones, list) or 'crl_hand__R' not in bones:
                raise ValueError('Driver hand pose request missing')
            active.append(index)
        previous_native, previous_time = native, time
    if not active or min(active) > 90 or max(active) < 95 or max(active) >= 100:
        raise ValueError('Driver hand signal interval absent before movement')
    return {'case_id': review['case_id'], 'indicator': 'driver_hand_signal',
            'signal_start_frame': min(active), 'signal_end_frame': max(active),
            'source_sha256': {name: sha(root / name) for name in names},
            'visual_visibility_verified': False,
            'original_review_declared': review['review_kind'] == 'original_source_review',
            'physical_acceptance_claimed': False, 'legal_verdict': None}
