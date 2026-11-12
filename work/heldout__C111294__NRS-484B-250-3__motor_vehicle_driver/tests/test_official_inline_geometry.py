import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parents[1]


class OfficialInlineGeometryTests(unittest.TestCase):
    def test_both_phases_and_fallbacks_require_same_native_binding(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        for entry in manifest['cases']:
            if not entry['case_id'].endswith(('__official_device_control', '__official_device_green_phase')):
                continue
            green = entry['case_id'].endswith('__official_device_green_phase')
            for candidate, construction_name in [('primary', entry['construction'])] + [
                (row['id'], row['construction']) for row in entry['candidates']
            ]:
                with self.subTest(case=entry['case_id'], candidate=candidate):
                    construction = json.loads((HERE / construction_name).read_text())
                    files = {row['path']: row['content'] for row in construction['files']}
                    runner = files['runner.py']
                    self.assertEqual(files['official_geometry_binding.py'],
                                     (HERE / 'official_geometry_binding.py').read_text())
                    self.assertIn('require_expected_geometry(', runner)
                    self.assertIn("output / 'official_geometry_binding.json'", runner)
                    self.assertIn("parser.add_argument('--expected-geometry')", runner)
                    self.assertEqual('max_spawns=600' in runner, candidate == 'fallback1')
                    self.assertEqual('.18 * (speed_mps - speed)' in runner,
                                     candidate == 'fallback2')
                    self.assertEqual("TrafficLightState.Green" in runner, green)
                    self.assertEqual('selected_signal.set_state(signal_previous_state)' in runner,
                                     green)


if __name__ == '__main__':
    unittest.main()
