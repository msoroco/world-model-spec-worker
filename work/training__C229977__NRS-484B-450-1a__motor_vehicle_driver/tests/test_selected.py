import json
from pathlib import Path
import unittest
from runner import check, footprint


class Selected(unittest.TestCase):
    def test_selected(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(footprint([[0, 0, 0], [1, 0, 0], [1, 1, 0],
                                        [0, 1, 0], [0, 0, 1], [1, 0, 1],
                                        [1, 1, 1], [0, 1, 1]])), 4)

    def test_bad_identity(self):
        config = json.loads(Path('config.json').read_text())
        config['cell_id'] = 'C0'
        with self.assertRaisesRegex(ValueError, 'frozen identity'):
            check(config)

    def test_degenerate_body(self):
        with self.assertRaisesRegex(ValueError, 'no footprint'):
            footprint([[0, 0, 0]] * 8)


if __name__ == '__main__':
    unittest.main()
