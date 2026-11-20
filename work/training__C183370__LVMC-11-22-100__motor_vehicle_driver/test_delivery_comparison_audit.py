"""The comparison audit must reject changes outside its measured variable."""
import copy
import unittest

from delivery_comparison_audit import validate_fixed_context


class FixedContextTests(unittest.TestCase):
    def setUp(self):
        self.config = {'assignment_id': 'case-assignment', 'actor': 'motor_vehicle_driver',
                       'cell_id': 'C183370', 'law_id': 'LVMC-11-22-100',
                       'cameras': ['overview', 'approach', 'reference_corner',
                                   'driver_reference'],
                       'duration_s': 30, 'rate_hz': 20, 'frames': 600,
                       'controller_knobs': {'speed_mps': 4.0},
                       'recording_description': {'source_frames': 600}}
        self.readback = {'plan': {'map_name': 'original-cell',
                                  'repair_polygon_xy_m': [[0, 0], [1, 0], [1, 1]],
                                  'control_kind': 'barrier'},
                         'pavement_road_id': 210,
                         'control_type_id': 'static.prop.trafficwarning'}

    def test_same_context_passes(self):
        validate_fixed_context(self.config, copy.deepcopy(self.config),
                               self.readback, copy.deepcopy(self.readback))

    def test_changed_controller_fails(self):
        other = copy.deepcopy(self.config)
        other['controller_knobs']['speed_mps'] = 5.0
        with self.assertRaisesRegex(ValueError, 'fixed capture config changed'):
            validate_fixed_context(self.config, other, self.readback,
                                   copy.deepcopy(self.readback))

    def test_changed_pavement_fails(self):
        other = copy.deepcopy(self.readback)
        other['plan']['repair_polygon_xy_m'][0] = [2, 2]
        with self.assertRaisesRegex(ValueError, 'pavement or control context changed'):
            validate_fixed_context(self.config, copy.deepcopy(self.config),
                                   self.readback, other)


if __name__ == '__main__':
    unittest.main()
