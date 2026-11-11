"""Original hand-bone and bicycle-control readback; safety need stays unresolved."""
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

HANDS = ('crl_hand__L', 'crl_hand__R')


def capture_hands(rider, frame, time_s):
    bones = {item.name: item for item in rider.get_bones().bone_transforms}
    readback = {}
    for name in HANDS:
        item = bones.get(name)
        readback[name] = None if item is None else {
            'location': [float(item.relative.location.x), float(item.relative.location.y),
                         float(item.relative.location.z)],
            'rotation_deg': [float(item.relative.rotation.pitch),
                             float(item.relative.rotation.yaw), float(item.relative.rotation.roll)]}
    return {'frame': frame, 'time_s': time_s, 'rider_id': str(rider.id),
            'hand_bone_readback': readback, 'physical_handlebar_contact_verified': None}


def capture_stability(trace, frame, time_s, command):
    return {'frame': frame, 'time_s': time_s,
            'wheel_steer_angle_deg': trace.get('wheel_steer_angle_deg'),
            'speed_mps': trace.get('speed_mps'),
            'accel_longitudinal_mps2': trace.get('accel_longitudinal_mps2'),
            'commanded_steer': command['steer'],
            'control_stability_judgment': None}


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(attempt):
    root = Path(attempt)
    names = ('video_frames.jsonl', 'rider_context.json', 'hand_contact_readback.jsonl',
             'control_stability.jsonl', 'hand_contact_review.jsonl', 'driver_reference.mkv')
    paths = {name: root / name for name in names}
    for name, path in paths.items():
        if not path.is_file() or not path.read_bytes():
            raise ValueError('Missing required source: ' + name)
    mapping, bones, stability, reviews = (_rows(paths[name]) for name in
        ('video_frames.jsonl', 'hand_contact_readback.jsonl',
         'control_stability.jsonl', 'hand_contact_review.jsonl'))
    context = json.loads(paths['rider_context.json'].read_text())
    if len(mapping) < 3 or len({len(rows) for rows in (mapping, bones, stability, reviews)}) != 1:
        raise ValueError('Hand-control original frame lengths differ')
    video_sha = sha256(paths['driver_reference.mkv'].read_bytes()).hexdigest()
    observed_contact = []
    peak_steer = 0.0
    for index, (frame, bone, control, review) in enumerate(zip(mapping, bones, stability, reviews)):
        identity = frame.get('carla_frame'), frame.get('time_s')
        if (frame.get('video_frame') != index or
                any((row.get('frame'), row.get('time_s')) != identity for row in (bone, control, review)) or
                bone.get('rider_id') != context.get('rider_id')):
            raise ValueError('Hand-control original frame identity differs')
        if review.get('source_video_sha256') != video_sha:
            raise ValueError('Stale hand-contact pixel review')
        for side in ('left_hand_contact', 'right_hand_contact'):
            value = review.get(side)
            if value is not None and type(value) is not bool:
                raise ValueError('Invalid hand-contact review')
        value = float(control['commanded_steer'])
        if not isfinite(value) or abs(value) > 1:
            raise ValueError('Invalid original steer command')
        peak_steer = max(peak_steer, abs(value))
        if review['left_hand_contact'] is True and review['right_hand_contact'] is True:
            observed_contact.append(frame['carla_frame'])
    return {'both_hands_visible_contact_frames': observed_contact,
            'hand_contact_review_complete': all(
                row['left_hand_contact'] is not None and row['right_hand_contact'] is not None
                for row in reviews),
            'peak_abs_commanded_steer': peak_steer,
            'both_hands_required_for_safety': None,
            'legal_signal_exception_judgment': None,
            'sources': {name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}}
