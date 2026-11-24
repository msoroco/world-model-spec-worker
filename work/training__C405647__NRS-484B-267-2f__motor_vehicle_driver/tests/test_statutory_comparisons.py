"""Source-shaped fixed-condition positive and negative comparison tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
TMP = HERE.parents[1] / '.runtime-work/c405647-267-2f/tmp'
SPEC = importlib.util.spec_from_file_location('statutory_comparisons', HERE / 'audit_statutory_comparisons.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StatutoryComparisons(unittest.TestCase):
    def test_hand_signal_only_difference_and_changed_lamp_negative(self):
        result = MODULE.audit('visible_hand_signal')
        self.assertEqual((result['fixed_vehicle_frames'], result['indicator_start_frame']), (600, 80))
        self.assertFalse(result['physical_acceptance_claimed'])
        self.changed_lamp_rejected('visible_hand_signal', 'draft-hand-signal/source',
                                   'hand_signal_review.json')

    def test_officer_direction_only_difference_and_changed_lamp_negative(self):
        result = MODULE.audit('officer_direction')
        self.assertEqual((result['fixed_vehicle_frames'], result['indicator_start_frame']), (600, 100))
        self.changed_lamp_rejected('officer_direction', 'draft-officer/source',
                                   'officer_direction.json')

    def changed_lamp_rejected(self, suffix, source, review_name):
        with tempfile.TemporaryDirectory(dir=TMP) as scratch:
            target = Path(scratch)
            shutil.copytree(HERE / source, target, dirs_exist_ok=True)
            poses = [json.loads(line) for line in (target / 'vehicle_poses.jsonl').read_text().splitlines()]
            poses[150]['emergency']['special1_light_on'] = not poses[150]['emergency']['special1_light_on']
            pose_path = target / 'vehicle_poses.jsonl'
            pose_path.write_text(''.join(json.dumps(row) + '\n' for row in poses))
            digest = hashlib.sha256(pose_path.read_bytes()).hexdigest()
            context = json.loads((target / 'emergency_context.json').read_text())
            context['native_source_hashes']['vehicle_poses.jsonl'] = digest
            (target / 'emergency_context.json').write_text(json.dumps(context) + '\n')
            review = json.loads((target / review_name).read_text())
            review['source_sha256']['vehicle_poses.jsonl'] = digest
            (target / review_name).write_text(json.dumps(review) + '\n')
            with self.assertRaisesRegex(ValueError, 'Fixed frame, vehicle path or flashing-light program differs'):
                MODULE.audit(suffix, target)


if __name__ == '__main__':
    unittest.main()
