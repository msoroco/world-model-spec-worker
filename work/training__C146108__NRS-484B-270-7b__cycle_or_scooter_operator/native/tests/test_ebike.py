import json
from pathlib import Path
import unittest

from ebike import ASSIST_CUTOFF_MPS, ClassOneSpecification, drive_step
import geometry_ebike
import runner


class ElectricBicycleTests(unittest.TestCase):
    def test_cell_and_witness(self):
        self.assertTrue(geometry_ebike.check()['passed'])
        plan = runner.check()
        self.assertEqual(plan['selected_statutory_subject'], 'electric_bicycle')
        self.assertEqual(plan['frames'], 600)
        self.assertEqual(len(plan['camera_names']), 4)

    def test_motor_and_pedal_interlocks(self):
        self.assertEqual(drive_step(3, 0, .05)['assist_power_watts'], 0)
        self.assertEqual(drive_step(ASSIST_CUTOFF_MPS, 70, .05)['assist_power_watts'], 0)
        with self.assertRaises(ValueError):
            ClassOneSpecification(motor_rated_watts=751).validate()

    def test_exact_config(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['cell_id'], 'C146108')
        self.assertEqual(config['rider_class'], 'electric_bicycle')
        self.assertEqual(config['duration_s'], 30)
        self.assertEqual(config['rate_hz'], 20)
        self.assertIn(config['rider_y_m'], (-1.75, -3.7))


if __name__ == '__main__':
    unittest.main()
