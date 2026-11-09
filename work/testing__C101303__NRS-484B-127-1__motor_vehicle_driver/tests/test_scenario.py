import sys
import unittest
import xml.dom.minidom
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scenario as S


class ScenarioTests(unittest.TestCase):
    def test_road_xml_parses_with_two_same_direction_lanes(self):
        doc = xml.dom.minidom.parseString(S.opendrive_xml())
        lanes = doc.getElementsByTagName('right')[0].getElementsByTagName('lane')
        self.assertEqual([l.getAttribute('id') for l in lanes], ['-1', '-2'])
        self.assertEqual(len(doc.getElementsByTagName('left')[0].childNodes), 0)

    def test_crest_is_continuous_and_peaks_inside_curve(self):
        lo, hi = S.CREST_S_M - S.CREST_VERTICAL_CURVE_M / 2, S.CREST_S_M + S.CREST_VERTICAL_CURVE_M / 2
        self.assertAlmostEqual(S.elevation_m(lo - 1e-9), S.elevation_m(lo + 1e-9), 6)
        self.assertAlmostEqual(S.elevation_m(hi - 1e-9), S.elevation_m(hi + 1e-9), 6)
        peak = max(range(0, 1200), key=S.elevation_m)
        self.assertTrue(lo < peak < hi)

    def test_each_case_changes_one_declared_variable_group(self):
        groups = {'closer': {'initial_gap_m', 'gap_hold_m'}, 'faster_ego': {'ego_set_speed_mps', 'lead_speed_mps'},
                  'slower_lead': {'lead_speed_mps'}, 'lead_brakes': {'lead_event'}, 'queued_traffic': {'queued_vehicle'},
                  'wet_surface': {'wetness', 'precipitation_deposits', 'precipitation', 'tire_friction'}, 'following_ends': {'lead_event'}}
        self.assertEqual(S.changed_from_base('base'), [])
        for name, keys in groups.items():
            self.assertEqual(set(S.changed_from_base(name)), keys, name)

    def test_lane_changes_cover_the_crest_in_every_case(self):
        for name in S.VARIANTS:
            rows = S.preview(name)
            self.assertEqual(rows[0]['ego_lane_id'], -1)
            self.assertEqual(rows[-1]['ego_lane_id'], -2, name)
            start = next(r for r in rows if r['ego_s_m'] >= S.LANE_CHANGE_TRIGGER_S_M)['ego_s_m']
            self.assertTrue(S.CREST_S_M - S.CREST_VERTICAL_CURVE_M / 2 <= start <= S.CREST_S_M + S.CREST_VERTICAL_CURVE_M / 2)
            self.assertLess(max(r['lead_s_m'] for r in rows), S.ROAD_LENGTH_M)

    def test_following_exists_before_lane_change_except_it_ends_when_declared(self):
        for name in S.VARIANTS:
            rows = S.preview(name)
            before = [r for r in rows if r['ego_lane_id'] == -1]
            self.assertTrue(all(r['bumper_gap_m'] is not None for r in before[:100]), name)
        ends = S.preview('following_ends')
        self.assertTrue(any(r['bumper_gap_m'] is None for r in ends if r['ego_lane_id'] == -1))

    def test_controllers_are_bounded_and_deterministic(self):
        p = S.case_params('base')
        self.assertEqual(S.ego_target_speed(p, None, 5.0), p['ego_set_speed_mps'])
        self.assertLess(S.ego_target_speed(p, 5.0, 5.0), 5.0)
        pi = S.SpeedPI()
        throttle, brake = pi.step(10.0, 0.0)
        self.assertTrue(0 <= throttle <= 1 and brake == 0)
        self.assertEqual(S.preview('base')[100], S.preview('base')[100])
        self.assertLessEqual(abs(S.steer_command(50.0, 3.0, 10.0)), 1.0)

    def test_no_legal_judgment_fields(self):
        text = Path(S.__file__).read_text().lower()
        for word in ('compliant', 'violat', 'legal_verdict'):
            self.assertNotIn(word, text)

    def test_lead_speed_event_profiles(self):
        p = S.case_params('lead_brakes')
        self.assertEqual(S.lead_target_speed(p, 0.0), 13.4)
        self.assertEqual(S.lead_target_speed(p, 100.0), 8.0)


if __name__ == '__main__':
    unittest.main()
