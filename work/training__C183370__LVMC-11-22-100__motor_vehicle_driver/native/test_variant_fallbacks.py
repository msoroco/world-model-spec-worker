import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_variant_exact import FALLBACKS, build
from variant_bundle_runner import KNOBS


class VariantFallbackTest(unittest.TestCase):
    def test_three_fallbacks_change_distinct_actuation_or_camera_knobs(self):
        self.assertEqual(set(FALLBACKS), {'fallback1', 'fallback2', 'fallback3'})
        for route in ('crossing', 'avoidance'):
            primary = build('barrier', route)
            configurations = []
            for candidate in FALLBACKS:
                variant = build('barrier', route, candidate)
                self.assertEqual(variant['case_id'], primary['case_id'])
                self.assertEqual(variant['recording_description'], primary['recording_description'])
                self.assertEqual(variant['measurement_plan'], primary['measurement_plan'])
                config = next(item['content'] for item in variant['files'] if item['path'] == 'config.json')
                configurations.append(config)
                self.assertTrue(FALLBACKS[candidate]['trigger']['source'])
            self.assertEqual(len(set(configurations)), 3)
            self.assertEqual(len(KNOBS), 4)


if __name__ == '__main__':
    unittest.main()
