from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rider_signal_finalizer import analyze, build_result, CASE_ID, CAMERAS


def sources(root):
    (root / 'config.json').write_text(json.dumps({
        'selected_case_id': CASE_ID, 'law_id': 'NRS-484B-768-1',
        'cell_id': 'C111588', 'actor': 'cycle_or_scooter_operator',
        'case': {'recording_description': {'channels': [], 'context_inputs': [],
                                           'limitations': ['CPU fixture only']}}}))
    for name in CAMERAS:
        (root / name).write_bytes(b'CPU synthetic camera marker ' + name.encode())
    video_sha = sha256((root / 'driver_reference.mkv').read_bytes()).hexdigest()
    (root / 'rider_context.json').write_text(json.dumps({
        'rider_id': 'rider-1', 'device_type': 'bicycle',
        'device_type_source': 'original blueprint', 'on_roadway': True,
        'roadway_source': 'original lane review',
        'designated_turn_lane': {'value': None, 'source_ref': None},
        'both_hands_required_for_safety': {'value': None, 'source_ref': None}}))
    rows = {
        'video_frames.jsonl': [{'video_frame': i, 'carla_frame': i,
                                'time_s': i * .05} for i in range(4)],
        'trace.jsonl': [{'frame': i, 'time_s': i * .05} for i in range(4)],
        'rider_motion.jsonl': [{'frame': i, 'time_s': i * .05,
                                'rider_id': 'rider-1', 'rider_yaw_deg': (0, 0, 25, 70)[i]}
                               for i in range(4)],
        'rider_arm_bones.jsonl': [{'frame': i, 'time_s': i * .05,
                                  'rider_id': 'rider-1', 'bone': 'crl_arm__L',
                                  'commanded_raised': i == 1,
                                  'relative_roll_deg': 70 if i == 1 else 0}
                                 for i in range(4)],
        'rider_signal_review.jsonl': [{'frame': i, 'time_s': i * .05,
                                      'rider_id': 'rider-1',
                                      'source_video_sha256': video_sha,
                                      'visible_signal': i == 1,
                                      'signal_type': 'left_arm' if i == 1 else 'none'}
                                     for i in range(4)]}
    for name, items in rows.items():
        (root / name).write_text(''.join(json.dumps(item) + '\n' for item in items))


class SavedRiderTests(unittest.TestCase):
    def test_source_join_and_native_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            report = analyze(root)
            result = build_result(root, report)
            sys.path.insert(0, str(Path(__file__).resolve().parents[3] /
                                   'runtime' / 'scenario_pipeline'))
            from worker_exchange.native_output import validate_result
            validate_result(result)
            self.assertEqual(result['measured_values']['rider_turn_signal_observation']
                             ['pre_turn_visible_signal_frames'], [1])
            self.assertFalse(result['physical_acceptance_claimed'])

    def test_missing_camera_or_stale_arm_join_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            (root / 'approach.mkv').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required original source'):
                analyze(root)
            sources(root)
            bone = root / 'rider_arm_bones.jsonl'
            rows = [json.loads(line) for line in bone.read_text().splitlines()]
            rows[1]['rider_id'] = 'other'
            bone.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'source/frame-map join failed'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
