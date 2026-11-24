import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crest_crossing import assess


def samples(stations):
    grades = [{'s_m': s, 'z_m': z, 'source_ref': 'native-map'}
              for s, z in ((0, 0), (100, 1), (200, 3), (250, 4), (300, 3))]
    motion = [{'frame_id': i + 10, 'time_s': i / 20,
               'ego_s_m': station, 'source_ref': f'native-frame-{i + 10}'}
              for i, station in enumerate(stations)]
    return grades, motion


class CrestCrossingTests(unittest.TestCase):
    def test_original_crossing_and_postcrest_are_distinct(self):
        grade, motion = samples([100, 180, 249, 250, 251, 280])
        result = assess(grade, motion, approach_start_m=100)
        self.assertEqual(result['crossing_frame_id'], 13)
        self.assertEqual(result['first_postcrest_frame_id'], 14)
        self.assertEqual(result['source_refs'],
                         ['native-frame-10', 'native-frame-13', 'native-frame-14'])

    def test_rejects_never_crossed_or_only_touching_crest(self):
        grade, motion = samples([100, 180, 249, 249.5])
        with self.assertRaisesRegex(ValueError, 'crossing'):
            assess(grade, motion, approach_start_m=100)
        grade, motion = samples([100, 180, 249, 250])
        with self.assertRaisesRegex(ValueError, 'postcrest'):
            assess(grade, motion, approach_start_m=100)

    def test_rejects_reverse_or_unsourced_motion(self):
        grade, motion = samples([100, 180, 249, 250, 251])
        motion[2]['ego_s_m'] = 179
        with self.assertRaisesRegex(ValueError, 'reversed'):
            assess(grade, motion, approach_start_m=100)
        grade, motion = samples([100, 180, 249, 250, 251])
        motion[3]['source_ref'] = ''
        with self.assertRaisesRegex(ValueError, 'source-bound'):
            assess(grade, motion, approach_start_m=100)


if __name__ == '__main__':
    unittest.main()
