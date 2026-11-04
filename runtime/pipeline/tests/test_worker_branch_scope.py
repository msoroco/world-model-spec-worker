"""The frozen assignment branch schema differs between delivery batches."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scenario_pipeline'))
from worker_exchange.preparation import validate_selected_branch


class BranchScopeTests(unittest.TestCase):
    def test_singular_witness_still_requires_exact_match(self):
        validate_selected_branch({'selected_branch': 'left turn'}, {'branch': 'left turn'})
        with self.assertRaisesRegex(ValueError, 'Selected witness branch changed'):
            validate_selected_branch({'selected_branch': 'right turn'}, {'branch': 'left turn'})

    def test_plural_records_do_not_imply_one_selected_label(self):
        records = [
            {'branch': 'left turn', 'source_index': 156},
            {'branch': 'left turn', 'source_index': 253},
            {'source_index': 9},
        ]
        validate_selected_branch({'selected_branch': None}, {'branches': records})
        validate_selected_branch({'selected_branch': 'approach near centerline'},
                                 {'branches': records})
        validate_selected_branch({'selected_branch': None},
                                 {'branches': [{'source_index': 1}]})

    def test_plural_records_must_be_nonempty_objects(self):
        for value in (None, [], 'left turn', [None], ['left turn']):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Missing frozen branch records'):
                validate_selected_branch({'selected_branch': None}, {'branches': value})
        with self.assertRaisesRegex(ValueError, 'Missing frozen branch records'):
            validate_selected_branch({'selected_branch': None}, {})


if __name__ == '__main__':
    unittest.main()
