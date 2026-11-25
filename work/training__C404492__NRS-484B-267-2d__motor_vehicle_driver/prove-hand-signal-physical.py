"""CPU physical-plan checks for the unselected driver-hand-signal case."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check(poses, frames):
    if len(poses) != 600 or len(frames) != 600:
        raise ValueError('Complete 600-frame source episode required')
    for index, (pose, frame) in enumerate(zip(poses, frames)):
        if (pose.get('video_frame') != index or frame.get('video_frame') != index
                or pose.get('native_frame') != frame.get('native_frame')
                or abs(float(frame.get('time_s', -1)) - index / 20) > 1e-4
                or set(frame.get('camera_native_frames', {})) !=
                {'overview', 'approach', 'reference_corner', 'driver_reference'}):
            raise ValueError('Original frame, time or camera join differs')
        if any(value != frame['native_frame']
               for value in frame['camera_native_frames'].values()):
            raise ValueError('Camera frame differs from Native source frame')
    before, preparation, travel = poses[:80], poses[80:120], poses[120:]
    signal_ids = {row['emergency'].get('driver_signal_actor_id') for row in poses}
    if len(signal_ids) != 1 or not all(type(value) is int for value in signal_ids):
        raise ValueError('Driver hand signal actor identity not source-joined')
    if (any(row['emergency']['speed_mps'] != 0 or
            row['emergency'].get('driver_hand_signal_visible') is not False
            for row in before)
            or any(row['emergency']['speed_mps'] != 0 or
                   row['emergency'].get('driver_hand_signal_visible') is not True
                   for row in preparation)
            or any(row['emergency']['speed_mps'] <= 0 or
                   row['emergency'].get('driver_hand_signal_visible') is not False
                   for row in travel)):
        raise ValueError('Stationary driver hand signal and subsequent travel phases differ')
    if poses[-1]['emergency']['x_m'] - poses[0]['emergency']['x_m'] <= 80:
        raise ValueError('Source vehicle travel incomplete')
    return {'joined_frames': 600, 'stopped_frames': 120,
            'visible_preparation_frames': 40, 'subsequent_travel_frames': 480,
            'driver_signal_actor_id': next(iter(signal_ids))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    poses_path = args.attempt / 'vehicle_poses.jsonl'
    frames_path = args.attempt / 'video_frames.jsonl'
    poses, frames = rows(poses_path), rows(frames_path)
    measured = check(poses, frames)
    negatives = []
    for name, changed_poses, changed_frames in (
            ('missing_frame', poses[:-1], frames),
            ('missing_driver_hand_signal',
             [{**row, 'emergency': {**row['emergency'],
                                   'driver_hand_signal_visible': False}}
              for row in poses], frames),
            ('movement_during_hand_signal',
             [{**row, 'emergency': {**row['emergency'],
                                   'speed_mps': 0.5 if i == 100 else row['emergency']['speed_mps']}}
              for i, row in enumerate(poses)], frames),
            ('changed_camera_frame', poses,
             [{**row, 'camera_native_frames':
               {**row['camera_native_frames'], 'overview': -1}}
              if i == 80 else row for i, row in enumerate(frames)])):
        try:
            check(changed_poses, changed_frames)
        except ValueError:
            negatives.append(name)
        else:
            raise AssertionError('Invalid physical diagnostic accepted: ' + name)
    proof = {'format': 'c404492-hand-signal-physical-plan-v1',
             'case_id': 'training__C404492__NRS-484B-267-2d__motor_vehicle_driver__preparing_hand_signal',
             'source_sha256': {'vehicle_poses.jsonl': sha(poses_path),
                               'video_frames.jsonl': sha(frames_path)},
             'measured': measured, 'rejected': negatives,
             'diagnostic_only': True, 'original_native_observed': False,
             'physical_acceptance_claimed': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'case_id': proof['case_id'], 'measured': measured,
                      'negative_checks': len(negatives),
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
