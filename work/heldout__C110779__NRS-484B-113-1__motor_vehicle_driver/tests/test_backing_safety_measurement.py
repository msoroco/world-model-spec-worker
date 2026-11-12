import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backing_safety_measurement import measure


class BackingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.motion = [{'frame': 30 + i, 'time_s': i * .05,
                        'ego': {'x_m': -i, 'y_m': 0, 'body_radius_m': 1},
                        'ego_heading_xy': [1, 0], 'ego_velocity_xy': [-2, 0],
                        'participants': {'other_1': {'x_m': -8, 'y_m': 0,
                                                     'body_radius_m': 1,
                                                     'speed_mps': 6 - i}}}
                       for i in range(4)]
        self.contacts = [{'frame': 30 + i, 'time_s': i * .05,
                          'contact_actor_ids': ['other_1'] if i == 3 else []}
                         for i in range(4)]
        self.context = {'participants': {'other_1': {
            'kind': 'vehicle', 'position_motion_purpose_source': 'original actor route and transform',
            'highway_use_source': 'original map lane and camera review'}}}

    def write(self):
        (self.root / 'backing_motion.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in self.motion))
        (self.root / 'backing_contacts.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in self.contacts))
        (self.root / 'backing_context.json').write_text(json.dumps(self.context))

    def result(self):
        return measure(self.root / 'backing_motion.jsonl',
                       self.root / 'backing_contacts.jsonl',
                       self.root / 'backing_context.json')

    def test_measures_reverse_window_gap_bearing_braking_and_contact(self):
        self.write()
        result = self.result()
        self.assertEqual((result['backing_onset_frame'], result['backing_end_frame']), (30, 33))
        self.assertEqual(result['contact_frames_during_backing'], [33])
        self.assertEqual(result['minimum_surface_gap_during_backing_m']['other_1'], 3)
        self.assertAlmostEqual(result['minimum_sampled_surrounding_acceleration_during_backing_mps2']['other_1'], -20)
        self.assertEqual(result['observations'][0]['relative_bearings_deg']['other_1'], 180)
        self.assertIsNone(result['observations'][0]['sampled_time_to_conflict_s']['other_1'])
        self.assertAlmostEqual(result['observations'][1]['sampled_time_to_conflict_s']['other_1'], .25)
        self.assertAlmostEqual(result['minimum_sampled_time_to_conflict_during_backing_s']['other_1'], .15)
        self.assertIsNone(result['interference_legal_judgment'])

    def test_time_to_conflict_requires_observed_closure(self):
        for row in self.motion:
            row['participants']['other_1']['x_m'] = -8 - 2 * (row['frame'] - 30)
        self.write()
        result = self.result()
        self.assertIsNone(result['minimum_sampled_time_to_conflict_during_backing_s']['other_1'])

    def test_rejects_contact_join_and_uncited_traffic_context(self):
        self.contacts[1]['frame'] = 40
        self.write()
        with self.assertRaisesRegex(ValueError, 'contact/motion frame join'):
            self.result()
        self.contacts[1]['frame'] = 31
        self.context['participants']['other_1']['highway_use_source'] = ''
        self.write()
        with self.assertRaisesRegex(ValueError, 'independently cited context'):
            self.result()

    def test_forward_only_activation_control_and_interrupted_backing(self):
        for row in self.motion:
            row['ego_velocity_xy'] = [2, 0]
        self.write()
        result = self.result()
        self.assertIsNone(result['backing_onset_frame'])
        self.assertIsNone(result['minimum_surface_gap_during_backing_m']['other_1'])
        self.motion[0]['ego_velocity_xy'] = [-2, 0]
        self.motion[2]['ego_velocity_xy'] = [-2, 0]
        self.write()
        with self.assertRaisesRegex(ValueError, 'unreviewed interruption'):
            self.result()

    def test_rejects_missing_original_contact_and_changed_actor(self):
        self.write()
        (self.root / 'backing_contacts.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing original source'):
            self.result()
        self.motion[2]['participants']['wrong'] = self.motion[2]['participants'].pop('other_1')
        self.write()
        with self.assertRaisesRegex(ValueError, 'actor identities differ'):
            self.result()


if __name__ == '__main__':
    unittest.main()
