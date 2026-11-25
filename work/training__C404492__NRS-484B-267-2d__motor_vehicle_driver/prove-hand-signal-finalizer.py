"""Prove the distinct stationary-driver-hand branch with source-shaped data."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = HERE.name + '__preparing_hand_signal'
SOURCE = HERE / 'current-fixture' / 'preparing_movement'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(source, output):
    return subprocess.run([sys.executable, str(HERE / 'native/hand_signal_finalize.py'),
                           '--source-dir', str(source), '--case', CASE,
                           '--output', str(output), '--diagnostic'],
                          capture_output=True, text=True)


def main():
    with tempfile.TemporaryDirectory(prefix='c404492-hand-finalizer-',
                                     dir=REPO / '.runtime-work') as temporary:
        source = Path(temporary) / 'source'
        source.mkdir()
        for name in ('video_frames.jsonl', 'trace.jsonl', 'vehicle_poses.jsonl',
                     'emergency_context.json'):
            shutil.copy2(SOURCE / name, source / name)
        context_path = source / 'emergency_context.json'
        context = json.loads(context_path.read_text())
        context.update(case_id=CASE,
                       driver_hand_signal_visual_source='synthetic:driver-hand-pixels',
                       driver_signal_actor_identity_source='synthetic:driver-arm-id',
                       driver_signal_window_source='synthetic:window-geometry',
                       driver_signal_visual_review_source='synthetic:reviewed-hand-pixels',
                       driver_signal_reviewer='synthetic reviewer',
                       driver_signal_actor_id=3)
        context_path.write_text(json.dumps(context) + '\n')
        poses_path = source / 'vehicle_poses.jsonl'
        poses = [json.loads(line) for line in poses_path.read_text().splitlines()]
        stopped_x = poses[79]['emergency']['x_m']
        offset = poses[119]['emergency']['x_m'] - stopped_x
        for index, pose in enumerate(poses):
            vehicle = pose['emergency']
            vehicle['driver_signal_actor_id'] = 3
            vehicle['driver_hand_signal_visible'] = 80 <= index < 120
            vehicle.pop('visible_vehicle_movement', None)
            if 80 <= index < 120:
                vehicle['x_m'] = stopped_x
                vehicle['speed_mps'] = 0.0
            elif index >= 120:
                vehicle['x_m'] -= offset
        poses_path.write_text(''.join(json.dumps(row) + '\n' for row in poses))
        report = Path(temporary) / 'positive.json'
        positive = run(source, report)
        if positive.returncode:
            raise ValueError('Hand signal positive failed: ' + positive.stderr[-700:])
        measured = json.loads(report.read_text())
        if (measured['visible_preparation_frames'] != 40 or
                measured['statutory_branch'] != 'emergency_preparing_hand_signal'):
            raise ValueError('Hand signal measured branch differs')
        negatives = {}
        for key in ('driver_hand_signal_visual_source',
                    'driver_signal_actor_identity_source',
                    'driver_signal_window_source',
                    'driver_signal_visual_review_source',
                    'driver_signal_reviewer'):
            invalid = dict(context, **{key: None})
            context_path.write_text(json.dumps(invalid) + '\n')
            negatives[key] = run(source, Path(temporary) / (key + '.json')).returncode != 0
        context_path.write_text(json.dumps(context) + '\n')
        poses[100]['emergency']['driver_hand_signal_visible'] = False
        poses_path.write_text(''.join(json.dumps(row) + '\n' for row in poses))
        negatives['missing_hand_frame'] = run(source, Path(temporary) / 'missing.json').returncode != 0
        poses[100]['emergency']['driver_hand_signal_visible'] = True
        poses[100]['emergency']['speed_mps'] = 0.5
        poses_path.write_text(''.join(json.dumps(row) + '\n' for row in poses))
        negatives['moving_instead_of_signaling'] = run(source, Path(temporary) / 'moving.json').returncode != 0
        if not all(negatives.values()):
            raise ValueError('Unreviewed hand signal source escaped: ' + str(negatives))
    proof = {'format': 'c404492-hand-signal-finalizer-cpu-proof-v1',
             'case_id': CASE, 'statutory_branch': measured['statutory_branch'],
             'visible_hand_signal_frames': measured['visible_preparation_frames'],
             'finalizer_sha256': sha(HERE / 'native/hand_signal_finalize.py'),
             'measure_sha256': sha(HERE / 'measure_emergency.py'),
             'negative_rejections': negatives,
             'original_native_executed': False,
             'physical_acceptance_claimed': False}
    target = HERE / 'current-hand-signal-finalizer-proof.json'
    target.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'proof_sha256': sha(target),
                      'negative_rejections': len(negatives)}))


if __name__ == '__main__':
    main()
