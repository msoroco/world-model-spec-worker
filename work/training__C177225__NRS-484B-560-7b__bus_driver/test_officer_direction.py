import unittest

from officer_direction import Crossing, OfficerStop, target_control


class DirectedStopConstructionTest(unittest.TestCase):
    def setUp(self):
        self.layout = Crossing()

    def signal(self, direction):
        return OfficerStop('officer-1', 'bus-1', direction, 10, 12, 300,
                           'crossing-1', True)

    def control(self, direction, station, frame=40, obey=True, speed=8.0):
        return target_control(self.layout, self.signal(direction),
                              bus_id='bus-1', crossing_id='crossing-1',
                              direction=direction, station_m=station,
                              speed_mps=speed, frame=frame, obey=obey)

    def test_both_approaches_have_stop_before_rail_and_exit_space(self):
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                start = self.layout.approach_station(direction)
                stop = self.layout.stop_station(direction)
                exit_point = self.layout.exit_station(direction)
                self.assertLess(0, direction * (stop - start))
                self.assertLess(0, direction * (exit_point - stop))
                self.assertGreaterEqual(self.layout.exit_clearance_m,
                                        self.layout.bus_length_m)
                self.assertEqual('stop_before_rail',
                                 self.control(direction, stop - direction * 3)['requested'])

    def test_only_requested_behavior_differs_after_same_signal(self):
        for direction in (-1, 1):
            station = self.layout.stop_station(direction) - direction * 3
            obey = self.control(direction, station)
            contrast = self.control(direction, station, obey=False)
            self.assertTrue(obey['signal_governing'])
            self.assertTrue(contrast['signal_governing'])
            self.assertEqual(obey['distance_to_stop_m'], contrast['distance_to_stop_m'])
            self.assertEqual('continue_through_line', contrast['requested'])
            self.assertGreater(obey['brake'], contrast['brake'])

    def test_presence_alone_and_wrong_recipient_do_not_count(self):
        with self.assertRaisesRegex(ValueError, 'authorization'):
            OfficerStop('officer-1', 'bus-1', 1, 10, 12, 300,
                        'crossing-1', False).validate()
        with self.assertRaisesRegex(ValueError, 'does not govern'):
            target_control(self.layout, self.signal(1), bus_id='other-bus',
                           crossing_id='crossing-1', direction=1,
                           station_m=-30, speed_mps=8, frame=40, obey=True)
        self.assertFalse(self.control(1, -30, frame=11)['signal_governing'])

    def test_invalid_timing_and_clearance_rejected(self):
        with self.assertRaisesRegex(ValueError, 'issued before'):
            OfficerStop('officer-1', 'bus-1', 1, 20, 12, 300,
                        'crossing-1', True).validate()
        with self.assertRaisesRegex(ValueError, 'exit space'):
            Crossing(exit_clearance_m=8).validate()


if __name__ == '__main__':
    unittest.main()
