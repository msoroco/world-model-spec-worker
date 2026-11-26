import json
import unittest
from pathlib import Path
from runner import check

class BundleTests(unittest.TestCase):
    def test_exact_case_and_four_cameras(self):
        root = Path(__file__).resolve().parents[1]
        case_id = check(root)
        config = json.loads((root / 'config.json').read_text())
        self.assertEqual(config['selected_case_id'], case_id)
        self.assertEqual(len(config['cameras']), 4)
        self.assertEqual(config['frame_count'], 900)

if __name__ == '__main__':
    unittest.main()
