import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_school_comparison import audit, read


class SchoolComparisonTests(unittest.TestCase):
    def test_positive_and_changed_motion_rejected(self):
        self.assertTrue(audit()['fixed_conditions_verified'])
        diagnostic = read('diagnostic-prohibition_363.json')
        diagnostic['files']['u_turn_motion.jsonl'] += '\n'
        with self.assertRaisesRegex(ValueError, 'motion, cameras or map'):
            audit(candidate_diagnostic=diagnostic)

    def test_unsupported_legal_claim_rejected(self):
        diagnostic = copy.deepcopy(read('diagnostic-prohibition_363.json'))
        import json
        source = json.loads(diagnostic['files']['u_turn_363_school.json'])
        source['school_zone_candidate']['children_present'] = True
        diagnostic['files']['u_turn_363_school.json'] = json.dumps(source)
        with self.assertRaisesRegex(ValueError, 'legal alternatives'):
            audit(candidate_diagnostic=diagnostic)


if __name__ == '__main__':
    unittest.main()
