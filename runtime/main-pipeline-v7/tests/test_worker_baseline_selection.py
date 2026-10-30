"""Neutral case definitions do not count as selected delivery recordings."""
import unittest

from scenario_pipeline.worker_exchange.preparation import selected_proposal_case_ids


class BaselineSelectionTests(unittest.TestCase):
    def test_neutral_baseline_is_kept_out_of_selected_case_coverage(self):
        proposal = {'cases': [
            {'case_id': 'neutral', 'target_type': 'baseline'},
            {'case_id': 'stop', 'target_type': 'compliant_attempt'},
            {'case_id': 'roll', 'target_type': 'violating_attempt'},
        ]}
        self.assertEqual(selected_proposal_case_ids(proposal), {'stop', 'roll'})
        self.assertNotEqual(selected_proposal_case_ids(proposal), {'stop'})


if __name__ == '__main__':
    unittest.main()
