"""CPU checks for fixed conditions and observed activity contrasts."""
import copy
import unittest

from audit_original_pair import compare


class OriginalPairAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = []
        cls.passenger = []
        cls.merchandise = []
        for index in range(600):
            time_s = (index + 1) / 20
            row = {'video_frame': index, 'time_s': time_s,
                   'taxi_xyz_m': [5.25, 10, 0],
                   'taxi_velocity_xyz_mps': [0, 0, 0]}
            common = {'video_frame': index, 'time_s': time_s,
                      'observed_taxi_identity': True,
                      'observed_stand_location': 'outside_designated_stand',
                      'observed_speed_mps': 0.02,
                      'observed_door_open': 160 <= index < 400}
            cls.native.append(row)
            cls.passenger.append(dict(common,
                observed_activity='passenger_loading' if 160 <= index < 400 else 'no_activity',
                observed_occupant_count=2 if index < 400 else 3))
            cls.merchandise.append(dict(common,
                observed_activity='merchandise_loading' if 160 <= index < 400 else 'no_activity',
                observed_occupant_count=2))
        cls.left = {'requested_activity': 'passenger_loading',
                    'occupant_count_min': 2, 'occupant_count_max': 3}
        cls.right = {'requested_activity': 'merchandise_loading',
                     'occupant_count_min': 2, 'occupant_count_max': 2}

    def run_pair(self, left=None, right=None, left_native=None, right_native=None,
                 left_activity=None, right_activity=None):
        return compare(left or self.left, right or self.right,
                       left_native or self.native, right_native or self.native,
                       left_activity or self.passenger,
                       right_activity or self.merchandise)

    def test_synthetic_shape_fixed_pair(self):
        result = self.run_pair()
        self.assertTrue(result['fixed_taxi_stand_pose_speed_door_timing'])
        self.assertIsNone(result['legal_verdict'])

    def test_wrong_activity_and_exchange_rejected(self):
        with self.assertRaisesRegex(ValueError, 'activity contrast'):
            self.run_pair(right={'requested_activity': 'passenger_loading',
                                 'occupant_count_min': 2, 'occupant_count_max': 2})
        with self.assertRaisesRegex(ValueError, 'passenger exchange'):
            self.run_pair(left={'requested_activity': 'passenger_loading',
                                'occupant_count_min': 2, 'occupant_count_max': 2})

    def test_missing_frame_and_changed_pose_rejected(self):
        with self.assertRaisesRegex(ValueError, 'complete 600-frame'):
            self.run_pair(left_native=self.native[:-1])
        changed = copy.deepcopy(self.native)
        changed[300]['taxi_xyz_m'][0] += 1
        with self.assertRaisesRegex(ValueError, 'taxi pose'):
            self.run_pair(right_native=changed)

    def test_changed_stand_door_and_time_rejected(self):
        changed = copy.deepcopy(self.merchandise)
        changed[300]['observed_stand_location'] = 'designated_stand'
        with self.assertRaisesRegex(ValueError, 'outside-stand'):
            self.run_pair(right_activity=changed)
        changed = copy.deepcopy(self.merchandise)
        changed[300]['observed_door_open'] = False
        with self.assertRaisesRegex(ValueError, 'door'):
            self.run_pair(right_activity=changed)
        changed = copy.deepcopy(self.merchandise)
        changed[300]['time_s'] += 0.05
        with self.assertRaisesRegex(ValueError, 'frame/time'):
            self.run_pair(right_activity=changed)


if __name__ == '__main__':
    unittest.main()
