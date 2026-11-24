"""Exercise both exact timing requests against source-shaped diagnostic rows."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from advance_rear_signal import target
from measure_timing import CAMERAS, FRAMES, measure

CASE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(folder, suffix):
    folder = Path(folder)
    folder.mkdir(parents=True)
    case_id = CASE.name + '__' + suffix
    selected = target(suffix)
    with (folder / 'actor-sources.jsonl').open('x') as actor_file, \
         (folder / 'camera-frames.jsonl').open('x') as camera_file:
        for i in range(FRAMES):
            row = {'case_id': case_id, 'frame': i, 'time_s': i / 20,
                   'ego_lane_id': -1, 'rear_lane_id': -1,
                   'rear_is_behind': True, 'surface_gap_m': 12.0,
                   'ego_speed_mps': 0 if i >= 150 else max(0, 8 - max(0, i-120)*.27),
                   'ego_accel_longitudinal_mps2': -5.4 if 120 <= i < 150 else 0,
                   'brake_lamp_commanded': i >= selected['brake_lamp_command_frame'],
                   'brake_lamp_observed': i >= selected['brake_lamp_command_frame'],
                   'hand_signal': 'none'}
            actor_file.write(json.dumps(row, sort_keys=True) + '\n')
            for camera in CAMERAS:
                token = hashlib.sha256(f'{case_id}:{i}:{camera}'.encode()).hexdigest()
                camera_file.write(json.dumps({'frame': i, 'camera': camera,
                                               'rgb_sha256': token}, sort_keys=True) + '\n')
    return case_id


def prove():
    scratch = CASE.parents[1] / '.runtime-work' / 'c179480-413-3'
    scratch.mkdir(parents=True, exist_ok=True)
    entries = []
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        for suffix, before in (('witness_1', True), ('witness_2', False)):
            folder = Path(tmp) / suffix
            case_id = fixture(folder, suffix)
            result = measure(folder, case_id)
            assert result['signal_precedes_diagnostic_deceleration'] is before
            assert result['rear_same_lane_all_frames']
            assert not result['original_native_observed']
            assert result['legal_verdict'] is None
            rejected = []
            actor_path = folder / 'actor-sources.jsonl'
            original = actor_path.read_text()
            actor_path.write_text('\n'.join(original.splitlines()[:-1]) + '\n')
            try:
                measure(folder, case_id)
            except ValueError as error:
                rejected.append(str(error))
            actor_path.write_text(original)
            frame_path = folder / 'camera-frames.jsonl'
            original_frames = frame_path.read_text()
            frame_path.write_text('\n'.join(original_frames.splitlines()[:-1]) + '\n')
            try:
                measure(folder, case_id)
            except ValueError as error:
                rejected.append(str(error))
            assert len(rejected) == 2
            entries.append({'case_id': case_id, 'result': result,
                            'negative_rejections': rejected})
    receipt = {'format': 'c179480-source-timing-cpu-proof-v1',
               'assignment_sha256': sha(CASE.parents[1] / 'inputs' / CASE.name / 'assignment.json'),
               'case_plan_sha256': sha(CASE / 'case-plan.json'),
               'module_sha256': sha(CASE / 'measure_timing.py'),
               'entries': entries, 'passed': True,
               'source_kind': 'synthetic_cpu', 'original_native_observed': False,
               'delivery_ready': False}
    path = CASE / 'offline' / 'source-timing-proof.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(entries), 'negative_rejections': 4}))


if __name__ == '__main__':
    prove()
