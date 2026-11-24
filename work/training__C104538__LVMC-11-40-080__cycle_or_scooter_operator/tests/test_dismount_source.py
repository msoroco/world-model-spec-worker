"""Check dismount timing, walking pace, and source mutation rejection."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'native'))
from thirty_second import rows, validate


class DismountSourceTest(unittest.TestCase):
    def test_order_and_walking_pace(self):
        source = rows('dismounted_turn', 'primary')
        report = validate(source, 'dismounted_turn', 'primary')
        self.assertEqual((report['dismount_frame'], report['first_turn_frame']), (180, 220))
        self.assertEqual(report['frames'], 600)

    def test_mutated_posture_is_rejected(self):
        source = copy.deepcopy(rows('dismounted_turn', 'primary'))
        source[220]['mounted'] = True
        source[220]['walking_machine'] = False
        with self.assertRaisesRegex(ValueError, 'Dismount must precede turn and persist'):
            validate(source, 'dismounted_turn', 'primary')

    def test_fast_walking_source_is_rejected(self):
        source = copy.deepcopy(rows('dismounted_turn', 'primary'))
        source[230]['x_m'] += 1
        with self.assertRaisesRegex(ValueError, 'walking pace'):
            validate(source, 'dismounted_turn', 'primary')


if __name__ == '__main__':
    unittest.main()
