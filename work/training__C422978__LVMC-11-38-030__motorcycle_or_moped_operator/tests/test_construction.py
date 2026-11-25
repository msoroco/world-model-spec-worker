import json
from pathlib import Path
import unittest
from runner import check

class Construction(unittest.TestCase):
    def test_exact(self):
        c = json.loads(Path('config.json').read_text())
        r = check(Path('.'), c['case_suffix'], c['candidate_id'])
        self.assertEqual(r['track_rows'], 600)
        self.assertFalse(r['original_native_observed'])
    def test_swapped_witness_rejected(self):
        c = json.loads(Path('config.json').read_text())
        wrong = 'witness_2' if c['case_suffix'] == 'witness_1' else 'witness_1'
        with self.assertRaises(ValueError):
            check(Path('.'), wrong, c['candidate_id'])

if __name__ == '__main__':
    unittest.main()
