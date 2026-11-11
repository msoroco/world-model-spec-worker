import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u_turn_measurement import PROHIBITIONS, measure


class UTurnTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [
            {'frame': 20 + i, 'time_s': i * .05,
             'ego_yaw_deg': yaw,
             'ego': {'x_m': i, 'y_m': 0, 'body_radius_m': 1},
             'participants': {
                 'oncoming_1': {'x_m': 8 - i, 'y_m': 0, 'body_radius_m': 1,
                                'speed_mps': 8 - i},
                 'following_1': {'x_m': -5, 'y_m': 0, 'body_radius_m': 1,
                                 'speed_mps': 5}}}
            for i, yaw in enumerate((0, 0, 40, 170))]
        self.context = {
            'prohibitions': {name: {'value': None, 'source_ref': None}
                             for name in PROHIBITIONS},
            'participant_roles': {
                'oncoming_1': {'role': 'oncoming', 'source_ref': 'original route and actor transform'},
                'following_1': {'role': 'following', 'source_ref': 'original route and actor transform'}}}

    def write(self):
        (self.root / 'u_turn_motion.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in self.rows))
        (self.root / 'u_turn_context.json').write_text(json.dumps(self.context))

    def result(self):
        return measure(self.root / 'u_turn_motion.jsonl', self.root / 'u_turn_context.json')

    def test_measures_whole_turn_clearance_and_braking_without_verdict(self):
        self.write()
        result = self.result()
        self.assertEqual((result['turn_onset_frame'], result['last_observed_frame']), (22, 23))
        self.assertAlmostEqual(result['net_heading_change_deg'], 170)
        self.assertEqual(result['participant_minimum_surface_gap_m']['oncoming_1'], 0)
        self.assertAlmostEqual(result['participant_minimum_sampled_acceleration_mps2']['oncoming_1'], -20)
        self.assertIsNone(result['safe_turn_legal_judgment'])

    def test_missing_prohibition_or_uncited_decision_rejected(self):
        del self.context['prohibitions']['NRS-484B-407']
        self.write()
        with self.assertRaisesRegex(ValueError, 'Every cited'):
            self.result()
        self.context['prohibitions']['NRS-484B-407'] = {'value': True, 'source_ref': None}
        self.write()
        with self.assertRaisesRegex(ValueError, 'needs cited source'):
            self.result()

    def test_discontinuous_frames_and_actor_identity_rejected(self):
        self.rows[2]['frame'] = 40
        self.write()
        with self.assertRaisesRegex(ValueError, 'not joined'):
            self.result()
        self.rows[2]['frame'] = 22
        del self.rows[2]['participants']['following_1']
        self.write()
        with self.assertRaisesRegex(ValueError, 'identities differ'):
            self.result()

    def test_missing_original_motion_and_nonfinite_speed_rejected(self):
        self.write()
        (self.root / 'u_turn_motion.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing original source'):
            self.result()
        self.rows[1]['participants']['oncoming_1']['speed_mps'] = float('nan')
        self.write()
        with self.assertRaisesRegex(ValueError, 'speed invalid'):
            self.result()


if __name__ == '__main__':
    unittest.main()
