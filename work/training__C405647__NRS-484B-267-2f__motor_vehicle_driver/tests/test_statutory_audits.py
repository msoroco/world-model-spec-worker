"""Source-shaped positive and negative tests for pending statutory alternatives."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
TMP = HERE.parents[1] / '.runtime-work/c405647-267-2f/tmp'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, HERE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StatutorySourceAudits(unittest.TestCase):
    def test_driver_hand_signal_and_absent_signal_negative(self):
        module = load('native/measure_hand_signal.py', 'hand_signal')
        source = HERE / 'draft-hand-signal/source'
        measured = module.measure(source)
        self.assertEqual((measured['signal_start_frame'], measured['signal_end_frame']), (80, 99))
        self.assertFalse(measured['visual_visibility_verified'])
        with tempfile.TemporaryDirectory(dir=TMP) as scratch:
            target = Path(scratch)
            for name in ('video_frames.jsonl', 'vehicle_poses.jsonl',
                         'driver_hand_track.jsonl', 'hand_signal_review.json'):
                shutil.copyfile(source / name, target / name)
            track = [json.loads(line) for line in (target / 'driver_hand_track.jsonl').read_text().splitlines()]
            for row in track:
                row['signal_active'] = False
                row['pose_bones_requested'] = []
            (target / 'driver_hand_track.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in track))
            review = json.loads((target / 'hand_signal_review.json').read_text())
            review['source_sha256']['driver_hand_track.jsonl'] = hashlib.sha256((target / 'driver_hand_track.jsonl').read_bytes()).hexdigest()
            (target / 'hand_signal_review.json').write_text(json.dumps(review) + '\n')
            with self.assertRaisesRegex(ValueError, 'signal interval absent'):
                module.measure(target)

    def test_vehicle_movement_indicator_and_no_motion_negative(self):
        module = load('audit_visible_preparation.py', 'visible_preparation')
        source = HERE / 'current-fixture/controlled_1'
        measured = module.audit(source)
        self.assertEqual(measured['first_motion_frame'], 100)
        self.assertFalse(measured['visual_visibility_verified'])
        with tempfile.TemporaryDirectory(dir=TMP) as scratch:
            target = Path(scratch)
            for name in ('video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json'):
                shutil.copyfile(source / name, target / name)
            poses = [json.loads(line) for line in (target / 'vehicle_poses.jsonl').read_text().splitlines()]
            for pose in poses:
                pose['emergency']['speed_mps'] = 0
                pose['emergency']['velocity_x_mps'] = 0
            (target / 'vehicle_poses.jsonl').write_text(''.join(json.dumps(pose) + '\n' for pose in poses))
            context = json.loads((target / 'emergency_context.json').read_text())
            context['native_source_hashes']['vehicle_poses.jsonl'] = hashlib.sha256((target / 'vehicle_poses.jsonl').read_bytes()).hexdigest()
            (target / 'emergency_context.json').write_text(json.dumps(context) + '\n')
            with self.assertRaisesRegex(ValueError, 'Stationary-to-moving'):
                module.audit(target)

    def test_officer_direction_join_and_absent_direction_negative(self):
        module = load('native/measure_officer.py', 'officer_direction')
        source = HERE / 'officer-source'
        measured = module.measure(source)
        self.assertEqual((measured['direction_start_frame'], measured['direction_end_frame']), (100, 200))
        self.assertFalse(measured['visual_direction_verified'])
        with tempfile.TemporaryDirectory(dir=TMP) as scratch:
            target = Path(scratch)
            for name in ('video_frames.jsonl', 'vehicle_poses.jsonl', 'officer_track.jsonl', 'officer_direction.json'):
                shutil.copyfile(source / name, target / name)
            track = [json.loads(line) for line in (target / 'officer_track.jsonl').read_text().splitlines()]
            for row in track:
                row['direction_active'] = False
            (target / 'officer_track.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in track))
            review = json.loads((target / 'officer_direction.json').read_text())
            review['source_sha256']['officer_track.jsonl'] = hashlib.sha256((target / 'officer_track.jsonl').read_bytes()).hexdigest()
            (target / 'officer_direction.json').write_text(json.dumps(review) + '\n')
            with self.assertRaisesRegex(ValueError, 'direction interval'):
                module.measure(target)

    def test_officer_direction_pose_request_missing_negative(self):
        module = load('native/measure_officer.py', 'officer_pose')
        source = HERE / 'draft-officer/source'
        self.assertEqual(module.measure(source)['direction_start_frame'], 100)
        with tempfile.TemporaryDirectory(dir=TMP) as scratch:
            target = Path(scratch)
            for name in ('video_frames.jsonl', 'vehicle_poses.jsonl',
                         'officer_track.jsonl', 'officer_direction.json'):
                shutil.copyfile(source / name, target / name)
            track = [json.loads(line) for line in (target / 'officer_track.jsonl').read_text().splitlines()]
            track[120]['pose_bones_requested'] = []
            (target / 'officer_track.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in track))
            review = json.loads((target / 'officer_direction.json').read_text())
            review['source_sha256']['officer_track.jsonl'] = hashlib.sha256((target / 'officer_track.jsonl').read_bytes()).hexdigest()
            (target / 'officer_direction.json').write_text(json.dumps(review) + '\n')
            with self.assertRaisesRegex(ValueError, 'pose request missing'):
                module.measure(target)


if __name__ == '__main__':
    unittest.main()
