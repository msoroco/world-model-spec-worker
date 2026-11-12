import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'roadway_physical_outcome.py'
spec = importlib.util.spec_from_file_location('roadway_physical_outcome', MODULE)
outcome = importlib.util.module_from_spec(spec)
spec.loader.exec_module(outcome)


class RoadwayPhysicalOutcomeTests(unittest.TestCase):
    def evidence(self, left=-0.2, final_x=1.0):
        measured = {'observations': [
            {'frame': 1, 'time_s': 0.0, 'minimum_body_right_offset_m': 0.4},
            {'frame': 2, 'time_s': 0.05, 'minimum_body_right_offset_m': left}],
            'sources': {'trace.jsonl': 'a', 'roadway.jsonl': 'b'}}
        trace = [{'frame': 1, 'time_s': 0.0, 'position': {'x': 0, 'y': 0}},
                 {'frame': 2, 'time_s': 0.05, 'position': {'x': final_x, 'y': 0}}]
        decodes = {name: {'source_sha256': name} for name in outcome.CAMERAS}
        reviews = {name: {'source_sha256': name, 'reviewed_frames': 2,
                          'subject_visible': True, 'roadway_visible': True}
                   for name in outcome.CAMERAS}
        return measured, trace, decodes, reviews

    def test_complete_both_branches(self):
        for suffix in outcome.CASES:
            with self.subTest(suffix=suffix):
                result = outcome.check_physical_outcome('assignment__'+suffix, *self.evidence())
                self.assertEqual(result['physical_checks']['maneuver']['status'], 'met')
                self.assertTrue(result['maneuver_completed'])
                self.assertFalse(result['legal_acceptance_claimed'])

    def test_incomplete_motion(self):
        for evidence in (self.evidence(left=0.1), self.evidence(final_x=0.0)):
            result = outcome.check_physical_outcome('assignment__three_lane', *evidence)
            self.assertEqual(result['physical_checks']['maneuver']['status'], 'not_met')
        measured, trace, decodes, reviews = self.evidence()
        measured['observations'][0]['minimum_body_right_offset_m'] = -0.3
        result = outcome.check_physical_outcome('assignment__three_lane', measured, trace, decodes, reviews)
        self.assertEqual(result['physical_checks']['maneuver']['status'], 'not_met')

    def test_missing_or_stale_evidence(self):
        measured, trace, decodes, reviews = self.evidence()
        reviews['overview']['source_sha256'] = 'stale'
        self.assertEqual(outcome.check_physical_outcome('assignment__posted_one_way',
                         measured, trace, decodes, reviews)['physical_checks']['maneuver']['status'], 'unverified')
        self.assertEqual(outcome.check_physical_outcome('assignment__posted_one_way',
                         None, trace, decodes, reviews)['physical_checks']['maneuver']['status'], 'unverified')


if __name__ == '__main__':
    unittest.main()
