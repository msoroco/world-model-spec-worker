import copy
import unittest

from measure_direction import derive_observation
from officer_direction import Crossing, OfficerStop


class SourceObservationTest(unittest.TestCase):
    def setUp(self):
        self.layout = Crossing()
        self.signal = OfficerStop('officer-1', 'bus-1', 1, 0, 1, 5,
                                  'crossing-1', True)
        self.bus = [
            {'native_frame': frame, 'actor_id': 'bus-1', 'station_m': station,
             'velocity_native_xyz_mps': [speed, 0, 0]}
            for frame, station, speed in ((0, -30, 8), (1, -20, 6),
                                           (2, -15, 4), (3, -14, 0),
                                           (4, -8, 3), (5, -2, 4))]
        self.officer = [
            {'native_frame': frame, 'actor_id': 'officer-1',
             'recipient_actor_id': 'bus-1', 'crossing_id': 'crossing-1',
             'direction': 1, 'authorized': True, 'hand_signal': 'STOP',
             'governing': frame >= 1, 'pose_control_applied': frame >= 1,
             'pose_bone_readback': 'crl_arm__R'}
            for frame in range(6)]
        self.video = [{'native_frame': frame, 'carla_frame': frame}
                      for frame in range(6)]

    def derive(self, bus=None, officer=None, video=None):
        return derive_observation(self.layout, self.signal,
                                  self.bus if bus is None else bus,
                                  self.officer if officer is None else officer,
                                  self.video if video is None else video,
                                  source_kind='synthetic_native_sample')

    def test_measured_stop_and_crossing_are_separate_observations(self):
        result = self.derive()
        self.assertEqual([3], result['stopped_before_line_frames'])
        self.assertEqual([4, 5], result['crossed_near_rail_frames'])
        self.assertTrue(result['observed_complete_stop_before_line'])
        self.assertTrue(result['observed_crossing_entry'])
        self.assertIsNone(result['legal_verdict'])

    def test_requested_stop_does_not_create_observed_stop(self):
        bus = copy.deepcopy(self.bus)
        bus[3]['velocity_native_xyz_mps'] = [2, 0, 0]
        self.assertFalse(self.derive(bus=bus)['observed_complete_stop_before_line'])

    def test_opposite_approach_uses_bus_front_and_near_rail(self):
        signal = OfficerStop('officer-1', 'bus-1', -1, 0, 1, 5,
                             'crossing-1', True)
        bus = copy.deepcopy(self.bus)
        officer = copy.deepcopy(self.officer)
        for row in bus:
            row['station_m'] *= -1
        for row in officer:
            row['direction'] = -1
        result = derive_observation(self.layout, signal, bus, officer,
                                    self.video,
                                    source_kind='synthetic_native_sample')
        self.assertEqual([3], result['stopped_before_line_frames'])
        self.assertEqual([4, 5], result['crossed_near_rail_frames'])

    def test_missing_or_mismatched_raw_signal_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not synchronized'):
            self.derive(officer=self.officer[:-1])
        officer = copy.deepcopy(self.officer)
        officer[3]['recipient_actor_id'] = 'other-bus'
        with self.assertRaisesRegex(ValueError, 'scope or timing'):
            self.derive(officer=officer)
        officer = copy.deepcopy(self.officer)
        officer[3]['pose_control_applied'] = False
        with self.assertRaisesRegex(ValueError, 'scope or timing'):
            self.derive(officer=officer)

    def test_missing_native_velocity_and_camera_frame_rejected(self):
        bus = copy.deepcopy(self.bus)
        del bus[2]['velocity_native_xyz_mps']
        with self.assertRaisesRegex(ValueError, 'Native bus station or velocity'):
            self.derive(bus=bus)
        video = copy.deepcopy(self.video)
        video[4]['carla_frame'] = 99
        with self.assertRaisesRegex(ValueError, 'same Native frame'):
            self.derive(video=video)


if __name__ == '__main__':
    unittest.main()
