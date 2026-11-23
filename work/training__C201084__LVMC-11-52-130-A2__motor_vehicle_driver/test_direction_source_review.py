"""Direction source joins reject wrong saved, frame and provenance claims."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import direction_source_review as review

ROOT = Path(__file__).resolve().parent
ATTEMPT = Path('.runtime-work/c201084-final-officer_direction-primary-compatibility')
EVENT = ROOT / 'selected-officer_direction-source-event.json'
SAVED = ROOT / 'selected-officer_direction-primary-saved.log'


class DirectionSourceReviewTest(unittest.TestCase):
    def test_two_selected_direction_traces(self):
        for case in ('officer_direction', 'device_direction'):
            result = review.build(
                case, Path('.runtime-work/c201084-final-' + case + '-primary-compatibility'),
                ROOT / ('selected-' + case + '-source-event.json'),
                ROOT / ('selected-' + case + '-primary-saved.log'))
            self.assertEqual(result['frames_joined'], 600)
            self.assertFalse(result['authority_verified'])
            self.assertFalse(result['physical_or_legal_completion_claimed'])

    def _with_saved(self, mutate):
        data = json.loads(SAVED.read_text())
        mutate(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'saved.json'
            path.write_text(json.dumps(data) + '\n')
            return review.build('officer_direction', ATTEMPT, EVENT, path)

    def test_wrong_saved_direction_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Direction trace differs'):
            self._with_saved(lambda data: data['original_source_hashes'].__setitem__(
                'police-officer-actor.jsonl', '0' * 64))

    def test_saved_case_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'saved processing identity'):
            self._with_saved(lambda data: data.__setitem__('case_id', 'wrong'))

    def test_stale_direction_frame_rejected(self):
        original = review.read_lines
        def altered(path):
            rows = original(path)
            if Path(path).name == 'police-officer-actor.jsonl':
                rows = copy.deepcopy(rows)
                rows[315]['frame'] += 1
            return rows
        with patch.object(review, 'read_lines', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'Direction frame'):
                review.build('officer_direction', ATTEMPT, EVENT, SAVED)

    def test_synthetic_authority_claim_rejected(self):
        original = review.read_lines
        def altered(path):
            rows = original(path)
            if Path(path).name == 'police-officer-actor.jsonl':
                rows = copy.deepcopy(rows)
                rows[400]['police_authority_verified'] = True
            return rows
        with patch.object(review, 'read_lines', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'provenance differs'):
                review.build('officer_direction', ATTEMPT, EVENT, SAVED)


if __name__ == '__main__':
    unittest.main()
