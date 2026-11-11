import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from physical_fixture import run


class TurnPhysicalProtocolTests(unittest.TestCase):
    def test_original_motion_outcomes_for_vehicle_and_pedestrian(self):
        for suffix in ('vehicle_left_indicator', 'ped_horn_audio'):
            case = ROOT.name + '__' + suffix
            for kind, expected in (('complete_motion', 'met'),
                                   ('incomplete_motion', 'not_met'),
                                   ('missing_evidence', 'unverified')):
                with self.subTest(case=case, kind=kind):
                    result = run(case, kind)
                    self.assertEqual(result['physical_checks']['maneuver']['status'], expected)
                    self.assertEqual(result['maneuver_completed'], expected == 'met')
                    self.assertFalse(result['actual_native_capture'])
                    self.assertFalse(result['physical_acceptance_claimed'])


if __name__ == '__main__':
    unittest.main()
