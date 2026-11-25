import unittest
import json
import tempfile
from pathlib import Path

from geometry import WIDTHS, check as geometry_check
from legal_context import REQUIRED, review_source
from runner import CAMERAS, check as runner_check, survey


class FakeCarla:
    class LaneType:
        Driving = 'driving'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeWaypoint:
    def __init__(self, x, y, width, wrong=False):
        self.road_id, self.lane_id, self.lane_width = 1, -2 if wrong else -1, width
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, 8)})()


class FakeWorld:
    def __init__(self, width, wrong=False):
        self.width, self.wrong = width, wrong

    def get_map(self):
        return self

    def get_waypoint(self, location, project_to_road, lane_type):
        return FakeWaypoint(location.x, location.y, self.width, self.wrong)


class NativeDraft(unittest.TestCase):
    def test_width_variants_and_capture(self):
        self.assertEqual(WIDTHS, {'controlled_1': 7.5, 'controlled_2': 6.0})
        self.assertEqual(geometry_check(7.5)['paved_width_m'], 7.5)
        self.assertEqual(geometry_check(6.0)['paved_width_m'], 6.0)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual([(name, width, height) for name, width, height, *_ in CAMERAS],
                         [('overview', 1920, 1080), ('approach', 1280, 720),
                          ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)])
        self.assertEqual(runner_check(7.5)['frames'], 600)
        self.assertEqual(runner_check(7.5, 9.1)['spawn_height_m'], 9.1)
        with self.assertRaisesRegex(ValueError, 'spawn height'):
            runner_check(7.5, 10.0)
        self.assertFalse(runner_check(7.5)['physical_acceptance_claimed'])

    def test_native_width_readback_gate(self):
        self.assertEqual(len(survey(FakeWorld(6.0), FakeCarla, 6.0)), 3)
        with self.assertRaisesRegex(RuntimeError, 'readback failed'):
            survey(FakeWorld(6.0, wrong=True), FakeCarla, 6.0)

    def test_independent_alley_source_is_explicit_and_fail_closed(self):
        packet = {'format': 'c178965-independent-alley-context-v1',
                  'review_status': 'independently_reviewed', 'reviewer': 'fixture reviewer',
                  'references': [{'path': 'synthetic-survey', 'sha256': 'a' * 64}],
                  'ordinance_effect': 'undetermined', 'site_match_review': 'undetermined'}
        packet.update({key: 'synthetic-' + key for key in REQUIRED})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'packet.json', root / 'retained.json'
            source.write_text(json.dumps(packet))
            receipt = review_source(source, target)
            self.assertEqual(receipt['site_match_review'], 'undetermined')
            self.assertEqual(target.read_bytes(), source.read_bytes())
            with self.assertRaisesRegex(ValueError, 'already copied'):
                review_source(source, target)
            packet['local_ordinance_review_source_id'] = ''
            source.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, 'fact binding missing'):
                review_source(source, root / 'rejected.json')
            self.assertFalse((root / 'rejected.json').exists())
