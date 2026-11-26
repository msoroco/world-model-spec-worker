import json
import sys
import unittest
from pathlib import Path


class ExactPriorityRequest(unittest.TestCase):
    def test_source_and_tracks(self):
        root = Path.cwd()
        config = json.loads((root / 'config.json').read_text())
        sys.path.insert(0, str(root / 'work' / config['assignment_id'] / 'native'))
        from check import check
        result = check(root)
        self.assertEqual(result['frames'], 600)
        self.assertFalse(result['original_native_observed'])


if __name__ == '__main__':
    unittest.main()
