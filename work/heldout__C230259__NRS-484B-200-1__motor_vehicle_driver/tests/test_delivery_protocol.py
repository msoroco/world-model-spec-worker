import importlib.util
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parents[1]
PREFIX = HERE.name + '__'
SUFFIXES = ('baseline_right', 'baseline_left', 'passing_left', 'closure_left',
            'three_lane_left', 'one_way_left', 'narrow_left')


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


physical = load('physical_fixture')
acceptance = load('acceptance_fixture')


class DeliveryProtocolTests(unittest.TestCase):
    def test_three_physical_outcomes_and_lifecycle_order(self):
        for suffix in SUFFIXES:
            case = PREFIX + suffix
            for kind, status in (('complete_motion', 'met'), ('incomplete_motion', 'not_met'),
                                 ('missing_evidence', 'unverified')):
                result = physical.evaluate(case, kind)
                self.assertEqual(result['physical_checks']['maneuver']['status'], status)
                self.assertFalse(result['actual_native_capture'])
        self.assertEqual(physical.lifecycle()['events'], physical.EVENTS)
        with self.assertRaisesRegex(ValueError, 'owner'):
            physical.lifecycle(out_of_order=True)

    def test_acceptance_source_bindings_and_stale_pixel_rejection(self):
        for suffix in SUFFIXES:
            case = PREFIX + suffix
            result = acceptance.audit(case)
            self.assertTrue(result['passed'])
            self.assertFalse(result['actual_pixels_reviewed'])
            with self.assertRaisesRegex(ValueError, 'Missing original-pixel review: approach'):
                acceptance.audit(case, negative=True)


if __name__ == '__main__':
    unittest.main()
