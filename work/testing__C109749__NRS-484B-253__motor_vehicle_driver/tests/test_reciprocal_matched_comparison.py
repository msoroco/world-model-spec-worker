import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent.parent
POSITIVE = REPO/'.runtime-work/c109749-reciprocal-yield-matched-delivery-v2/attempt'
NEGATIVE = REPO/'.runtime-work/c109749-reciprocal-no-yield-delivery-v1/attempt'
sys.path.insert(0,str(ROOT))
from reciprocal_matched_comparison_audit import compare_histories, compare
from reciprocal_yield_matched_observation import observe


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class ReciprocalMatchedComparisonTests(unittest.TestCase):
    def sources(self):
        positive = rows(POSITIVE/'interaction_history.jsonl')
        negative = rows(NEGATIVE/'interaction_history.jsonl')
        polygon = json.loads((POSITIVE/'intersection_geometry.json').read_text())['intersection_polygon_xy_m']
        return positive,negative,polygon

    def test_full_duration_fixed_motion_and_declared_response(self):
        positive,negative,polygon = self.sources()
        report = compare_histories(positive,negative,polygon)
        self.assertEqual(report['fixed_samples'],900)
        self.assertLess(report['positive_stop_frame'],report['negative_entry_frame'])
        self.assertFalse(observe(POSITIVE)['legal_verdict_asserted'])
        diagnostic = json.loads((ROOT/'reciprocal-matched-comparison-diagnostic.json').read_text())
        self.assertTrue(diagnostic['software_checks_passed'])
        self.assertFalse(diagnostic['passed'])

    def test_changed_fixed_subject_or_preturn_actor_rejected(self):
        positive,negative,polygon = self.sources()
        changed = copy.deepcopy(negative)
        changed[7]['ego']['position_xy_m'][0] += 1
        with self.assertRaisesRegex(ValueError,'Fixed ego trajectory'):
            compare_histories(positive,changed,polygon)
        changed = copy.deepcopy(negative)
        changed[2]['reciprocal']['position_xy_m'][0] += 1
        with self.assertRaisesRegex(ValueError,'Fixed pre-turn reciprocal'):
            compare_histories(positive,changed,polygon)

    def test_merely_continued_outside_approach_rejected(self):
        positive,negative,polygon = self.sources()
        changed = copy.deepcopy(negative)
        for row in changed[4:]:
            row['reciprocal']['position_xy_m']=[16,0]
            row['reciprocal']['body_vertices_xy_m']=[[15,-1],[17,-1],[17,1],[15,1]]
        with self.assertRaisesRegex(ValueError,'Declared stopped-outside versus moving-entry'):
            compare_histories(positive,changed,polygon)


if __name__=='__main__':
    unittest.main()
