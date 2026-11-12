import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u_turn_363_school import measure_school_candidate


def scene():
    waypoint = SimpleNamespace(road_id=7, lane_id=-1,
        transform=SimpleNamespace(location=SimpleNamespace(x=0, y=0)))
    return {'approach': waypoint}


def sign(label='SCHOOL ZONE', *, road_id=7, xy=(10, 2)):
    return {'landmark_id': 'A', 'road_id': road_id, 'xy_m': list(xy),
            'name': label, 'type': '274', 'value': ''}


class SchoolCandidateTests(unittest.TestCase):
    def test_mapped_candidate_retains_all_exception_unknowns(self):
        packet = measure_school_candidate(scene(), [sign()])
        self.assertEqual(packet['matching_landmarks'][0]['landmark_id'], 'A')
        for key in ('official_zone_designation', 'children_present',
                    'school_in_session', 'governing_body_exempt_period',
                    'operational_beacon', 'pupils_in_class',
                    'yellow_beacon_lights_flashing',
                    'sign_speed_limit_in_effect',
                    'legal_prohibition_applicable'):
            self.assertIsNone(packet[key])

    def test_wrong_road_and_distant_sign_rejected(self):
        with self.assertRaisesRegex(ValueError, 'No source-mapped'):
            measure_school_candidate(scene(), [sign(road_id=8), sign(xy=(100, 0))])

    def test_generic_school_word_is_not_zone_designation_candidate(self):
        with self.assertRaisesRegex(ValueError, 'No source-mapped'):
            measure_school_candidate(scene(), [sign('SCHOOL BUS')])


if __name__ == '__main__':
    unittest.main()
