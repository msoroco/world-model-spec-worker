import importlib.util
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location('truck_site', Path(__file__).resolve().parents[1] / 'truck_site.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class TruckSiteTests(unittest.TestCase):
    def test_one_way_site_and_statutory_gap_placement(self):
        source = site.validate_site()
        self.assertEqual(source['same_direction_lane_count'], 1)
        self.assertEqual(source['blueprint_ids'], list(site.TRUCK_BLUEPRINTS))
        for name, target in site.GAP_TARGETS_M.items():
            pair = site.initial_pair(name, 4.3, 5.1)
            measured = pair['lead_center_xy_m'][0] - 5.1 - (pair['ego_center_xy_m'][0] + 4.3)
            self.assertAlmostEqual(measured, target)
            self.assertEqual(pair['ego_center_xy_m'][1], pair['lead_center_xy_m'][1])
            envelope = site.validate_motion_envelope(pair, 5.1)
            self.assertGreater(envelope['remaining_margin_m'], 50)

    def test_rejects_oversize_and_nonfinite_body_lengths(self):
        for bad in (0, -1, float('inf'), float('nan'), True):
            with self.assertRaisesRegex(ValueError, 'half lengths'):
                site.initial_pair('gap_at_500ft', bad, 4)
        with self.assertRaisesRegex(ValueError, 'margins'):
            site.initial_pair('gap_at_500ft', 4, 1100)
        with self.assertRaisesRegex(ValueError, 'motion budget'):
            site.validate_motion_envelope(site.initial_pair('gap_at_500ft', 4, 5), 5, speed_mps=25)

    def test_rejects_added_opposing_lane(self):
        original = site.ROAD
        with tempfile.TemporaryDirectory() as folder:
            changed = Path(folder) / 'two_way.xodr'
            text = original.read_text().replace('<left />', '<left><lane id="1" type="driving" /></left>')
            changed.write_text(text)
            try:
                site.ROAD = changed
                with self.assertRaisesRegex(ValueError, 'single forward'):
                    site.validate_site()
            finally:
                site.ROAD = original


if __name__ == '__main__':
    unittest.main()
