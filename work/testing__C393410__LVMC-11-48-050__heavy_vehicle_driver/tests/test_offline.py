import json
import unittest
from pathlib import Path
from runner import check

class SelectedNightTruckOffline(unittest.TestCase):
    def test_exact_source_gate(self):
        root = Path(__file__).resolve().parents[1]
        selected = check(root)
        self.assertEqual(selected['case_id'], json.loads((root / 'config.json').read_text())['selected_case_id'])
        self.assertIn('unladen', selected['source_gate'])

if __name__ == '__main__':
    unittest.main()
