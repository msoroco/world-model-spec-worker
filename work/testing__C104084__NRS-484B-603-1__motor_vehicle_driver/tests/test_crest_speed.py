import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crest_speed import crest_station, measure


GRADE = [dict(s_m=s, z_m=z, source_ref=f'map:{i}') for i, (s, z) in enumerate(
    [(0, 0), (10, 2), (20, 6), (30, 3), (40, 0)])]


def history(speeds):
    return [dict(frame_id=i, time_s=i / 20, ego_s_m=s, ego_speed_mps=v,
                 other_s_m=40 - s, body_clearance_m=40 - 2 * s,
                 source_ref=f'native:{i}')
            for i, (s, v) in enumerate(zip((0, 5, 10, 15), speeds))]


class CrestSpeedTests(unittest.TestCase):
    def test_measured_crest_and_early_decrease(self):
        out = measure(GRADE, history((12, 11, 9, 8)), approach_start_m=0)
        self.assertEqual(out['crest_station_m'], 20)
        self.assertEqual(out['first_speed_decrease_frame_id'], 1)
        self.assertEqual(out['first_speed_decrease_station_m'], 5)
        self.assertEqual(out['speed_change_mps'], -4)

    def test_steady_speed_retains_no_decrease(self):
        out = measure(GRADE, history((12, 12, 12, 12)), approach_start_m=0)
        self.assertIsNone(out['first_speed_decrease_frame_id'])
        self.assertIsNone(out['first_speed_decrease_station_m'])

    def test_original_motion_required(self):
        frames = history((12, 12, 12, 12))
        del frames[1]['source_ref']
        with self.assertRaisesRegex(ValueError, 'source'):
            measure(GRADE, frames, approach_start_m=0)

    def test_noncrest_rejected(self):
        grade = [dict(s_m=i * 10, z_m=i, source_ref=f'map:{i}') for i in range(5)]
        with self.assertRaisesRegex(ValueError, 'crest'):
            crest_station(grade)

    def test_approach_cannot_use_postcrest_samples(self):
        frames = history((12, 11, 9, 8))
        frames[1]['ego_s_m'] = 21
        frames[2]['ego_s_m'] = 26
        frames[3]['ego_s_m'] = 30
        with self.assertRaisesRegex(ValueError, 'pre-crest'):
            measure(GRADE, frames, approach_start_m=0)


if __name__ == '__main__':
    unittest.main()
