import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from construction import build
from reciprocal_fallback import CASES, fallback


class ReciprocalFallback(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((ROOT / 'cases/inside_yield/diagnostic-map.json').read_text())

    def test_both_cases_preserve_comparison_variable_and_capture(self):
        controls = []
        for case in CASES:
            primary = build(case, self.packet)
            candidate = fallback(case, self.packet)
            self.assertEqual(candidate['capture'], primary['capture'])
            self.assertEqual(candidate['native_map_sha256'], primary['native_map_sha256'])
            self.assertEqual(candidate['ego_route'], primary['ego_route'])
            self.assertEqual(candidate['initial_opponent_route'], primary['initial_opponent_route'])
            self.assertEqual(candidate['later_opposing_route'], primary['later_opposing_route'])
            self.assertEqual(candidate['controller']['wait_for_later_opponent'],
                             primary['controller']['wait_for_later_opponent'])
            self.assertEqual(candidate['controller']['target_speed_mps'], 3.0)
            controls.append(candidate['controller']['wait_for_later_opponent'])
        self.assertEqual(controls, [True, False])

    def test_rejects_nonreciprocal_case(self):
        with self.assertRaisesRegex(ValueError, 'reciprocal cases only'):
            fallback(CASES[0].replace('reciprocal_yield', 'inside_yield'), self.packet)


if __name__ == '__main__':
    unittest.main()
