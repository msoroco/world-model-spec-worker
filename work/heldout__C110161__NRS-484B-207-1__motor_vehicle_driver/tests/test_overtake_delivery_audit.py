import json
from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake_delivery_audit import audit, REQUIRED
from test_overtake_measurement import box


class DeliverySourceAuditTests(unittest.TestCase):
    def test_original_source_and_saved_result_rechecks(self):
        case = 'heldout__C110161__NRS-484B-207-1__motor_vehicle_driver__left_pass_wide'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt = root / 'attempt'
            attempt.mkdir()
            (attempt / 'config.json').write_text(json.dumps({'selected_case_id': case}))
            rows = []
            for i, (x, y) in enumerate(((0, 4), (5, 4), (10, 4), (12, 2))):
                rows.append({'frame': 100 + i, 'time_s': i * .05,
                             'ego_id': 'ego', 'other_id': 'other',
                             'road_tangent_xy': [1, 0],
                             'ego_heading_xy': [1, 0], 'other_heading_xy': [1, 0],
                             'ego_corners': box(x, x + 4, y, y + 2),
                             'other_corners': box(5, 9, 0, 2)})
            (attempt / 'participant_footprints.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in rows))
            for name in REQUIRED - {'config.json', 'participant_footprints.jsonl'}:
                (attempt / name).write_text('small CPU source\n')
            (attempt / 'construction.json').write_text('{}\n')
            result = root / 'result.json'
            result.write_text(json.dumps({'case_id': case,
                'realized_observables': {'left_pass_clearance_m': {'value': 2},
                                         'return_clearance_m': {'value': 3}},
                'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}))
            digest = lambda path: sha256(path.read_bytes()).hexdigest()
            receipt = root / 'processing.json'
            receipt.write_text(json.dumps({
                'format': 'worker-saved-processing', 'case_id': case,
                'passed': True, 'recorded_only': True, 'originals_preserved': True,
                'missing_evidence': False, 'candidate_id': 'primary',
                'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
                'final_video_checks': {'passed': True},
                'original_source_hashes': {name: digest(attempt / name) for name in REQUIRED},
                'analysis_revision': {'construction_sha256': digest(attempt / 'construction.json')},
                'result': str(result), 'result_sha256': digest(result)}))
            self.assertTrue(audit(attempt, receipt)['source_integrity_passed'])
            (attempt / 'participant_footprints.jsonl').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'Original source changed'):
                audit(attempt, receipt)
            (attempt / 'participant_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Original source changed'):
                audit(attempt, receipt)


if __name__ == '__main__':
    unittest.main()
