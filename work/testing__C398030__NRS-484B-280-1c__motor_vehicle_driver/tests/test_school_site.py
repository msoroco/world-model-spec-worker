"""CPU construction checks for original school markers and actor placement."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import inspect_school
from road_scene import load_site, observed_encounter


class Marker:
    def __init__(self, identity, name, x, y):
        self.id, self.name = identity, name
        self.bounding_box = SimpleNamespace(location=SimpleNamespace(x=x, y=y))


class Map:
    def to_opendrive(self):
        return '<OpenDRIVE><road id="3"/></OpenDRIVE>'

    def get_waypoint(self, point):
        return SimpleNamespace(lane_type='driving', lane_width=4.0, road_id=3,
                               lane_id=1, transform=SimpleNamespace(
                                   rotation=SimpleNamespace(yaw=0),
                                   location=SimpleNamespace(y=0.0)))


class World:
    def __init__(self, markers):
        self.markers = markers

    def get_map(self):
        return Map()

    def get_environment_objects(self, label):
        return self.markers


CARLA = SimpleNamespace(CityObjectLabel=SimpleNamespace(TrafficSigns='traffic_signs'),
                        LaneType=SimpleNamespace(Driving='driving'),
                        Location=lambda **kwargs: SimpleNamespace(**kwargs))


def body(x, y, width):
    return [[x-width, y-width, 0], [x-width, y+width, 0],
            [x+width, y-width, 0], [x+width, y+width, 0]]


class SchoolSiteTests(unittest.TestCase):
    def setUp(self):
        scratch = Path('.runtime-work/c398030/tmp').resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name)
        self.scene = {"ego_spawn_offset_m": 20}
        self.markers = [Marker(11, 'School Zone Begin', -15, 2),
                        Marker(12, 'School Zone End', 15, 2)]

    def inspect(self, markers=None):
        return inspect_school(World(self.markers if markers is None else markers),
                              CARLA, self.scene, self.output)

    def test_readback_places_pedestrian_between_original_markers(self):
        site = self.inspect()
        self.assertEqual(site, load_site(self.output/'school-site.json'))
        self.assertEqual(site['pedestrian_start_xy_m'], [0, 3.5])
        self.assertEqual(site['ego_start_xy_m'], [-35, 0.0])
        self.assertEqual(site['ego_end_xy_m'], [35, 0.0])

    def test_missing_original_school_sign_rejected(self):
        with self.assertRaisesRegex(ValueError, 'original Native school'):
            self.inspect([self.markers[0]])

    def test_merely_named_school_flag_rejected(self):
        self.inspect()
        path = self.output/'school-site.json'
        site = json.loads(path.read_text())
        site['school_boundary_markers'] = []
        path.write_text(json.dumps(site))
        with self.assertRaisesRegex(ValueError, 'markers missing'):
            load_site(path)

    def test_stale_original_map_rejected(self):
        self.inspect()
        (self.output/'map.xodr').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'stale original school map'):
            load_site(self.output/'school-site.json')

    def test_actor_body_and_driver_source_checked(self):
        site = self.inspect()
        sample = {'ego_body_vertices_m': body(-5, 0, 1),
                  'pedestrian_body_vertices_m': body(0, 3.5, .2),
                  'ego_class': 'motor_vehicle', 'pedestrian_class': 'pedestrian',
                  'pedestrian_class_source': 42, 'driver_control_source': 'scripted',
                  'driver_observation_event': {'source': 'original_driver_input',
                                               'observed': True},
                  'ego_speed_mps': 4.0, 'ego_brake': .2}
        value = observed_encounter(site, sample)
        self.assertTrue(value['pedestrian_within_original_school_markers'])
        self.assertIsNone(value['legal_proper_caution_verdict'])
        sample['pedestrian_body_vertices_m'] = body(20, 3.5, .2)
        with self.assertRaisesRegex(ValueError, 'outside original school markers'):
            observed_encounter(site, sample)
        sample['pedestrian_body_vertices_m'] = body(0, 3.5, .2)
        sample['driver_observation_event'] = {'source': 'camera_visibility', 'observed': True}
        with self.assertRaisesRegex(ValueError, 'original input event'):
            observed_encounter(site, sample)


if __name__ == '__main__':
    unittest.main()
