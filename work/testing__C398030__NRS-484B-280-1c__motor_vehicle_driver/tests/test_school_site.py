"""CPU construction checks for original school markers and actor placement."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import Cameras, ego_spawn_transform, inspect_school
from road_scene import load_site, observed_encounter


class Marker:
    def __init__(self, identity, name, x, y):
        self.id, self.name = identity, name
        self.bounding_box = SimpleNamespace(location=SimpleNamespace(x=x, y=y))


class Map:
    def __init__(self, y_by_x=None, lane_by_x=None, yaw_by_x=None):
        self.y_by_x = y_by_x or (lambda x: 0.0)
        self.lane_by_x = lane_by_x or (lambda x: 1)
        self.yaw_by_x = yaw_by_x or (lambda x: 0.0)

    def to_opendrive(self):
        return '<OpenDRIVE><road id="3"/></OpenDRIVE>'

    def get_waypoint(self, point):
        return SimpleNamespace(lane_type='driving', lane_width=4.0, road_id=3,
                               lane_id=self.lane_by_x(point.x), transform=SimpleNamespace(
                                   rotation=SimpleNamespace(yaw=self.yaw_by_x(point.x)),
                                   location=SimpleNamespace(x=point.x, y=self.y_by_x(point.x), z=0.0)))


class World:
    def __init__(self, markers, mapping=None):
        self.markers, self.mapping = markers, mapping or Map()

    def get_map(self):
        return self.mapping

    def get_environment_objects(self, label):
        return self.markers


CARLA = SimpleNamespace(CityObjectLabel=SimpleNamespace(TrafficSigns='traffic_signs'),
                        LaneType=SimpleNamespace(Driving='driving'),
                        Location=lambda **kwargs: SimpleNamespace(**kwargs),
                        Rotation=lambda **kwargs: SimpleNamespace(**kwargs),
                        Transform=lambda location, rotation: SimpleNamespace(
                            location=location, rotation=rotation))


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

    def inspect(self, markers=None, mapping=None):
        return inspect_school(World(self.markers if markers is None else markers, mapping),
                              CARLA, self.scene, self.output)

    def test_readback_places_pedestrian_between_original_markers(self):
        site = self.inspect()
        self.assertEqual(site, load_site(self.output/'school-site.json'))
        self.assertEqual(site['pedestrian_start_xy_m'], [0, 3.5])
        self.assertEqual(site['ego_start_xy_m'], [-35, 0.0])
        self.assertEqual(site['ego_end_xy_m'], [35, 0.0])
        self.assertEqual(site['lane_route_samples'][0]['center_xy_m'], [-35.0, 0.0])
        self.assertEqual(site['lane_route_samples'][-1]['center_xy_m'], [35.0, 0.0])
        self.assertEqual(site['ego_spawn_yaw_deg'], 0.0)

    def test_nearly_straight_lane_uses_readback_at_both_endpoints(self):
        site = self.inspect(mapping=Map(y_by_x=lambda x: .1 if x < -20 else (.05 if x > 20 else 0)))
        self.assertEqual(site['ego_start_xy_m'], [-35.0, .1])
        self.assertEqual(site['ego_end_xy_m'], [35.0, .05])
        self.assertEqual(site, load_site(self.output/'school-site.json'))

    def test_curved_or_changed_lane_rejected(self):
        with self.assertRaisesRegex(ValueError, 'continuous straight driving lane'):
            self.inspect(mapping=Map(y_by_x=lambda x: 1 if x < -20 else 0))
        with self.assertRaisesRegex(ValueError, 'continuous straight driving lane'):
            self.inspect(mapping=Map(lane_by_x=lambda x: 2 if x > 20 else 1))
        with self.assertRaisesRegex(ValueError, 'continuous straight driving lane'):
            self.inspect(mapping=Map(yaw_by_x=lambda x: 3 if x < -20 else 0))

    def test_stale_or_missing_route_readback_rejected(self):
        site = self.inspect()
        path = self.output/'school-site.json'
        site['lane_route_samples'][0]['lane_id'] = 9
        path.write_text(json.dumps(site))
        with self.assertRaisesRegex(ValueError, 'route readback invalid'):
            load_site(path)
        site = self.inspect()
        site['lane_route_samples'] = [site['lane_route_samples'][0], site['lane_route_samples'][-1]]
        path.write_text(json.dumps(site))
        with self.assertRaisesRegex(ValueError, 'route readback invalid'):
            load_site(path)

    def test_spawn_rechecks_source_lane_and_uses_readback_yaw(self):
        site = self.inspect(mapping=Map(yaw_by_x=lambda x: .4 if x < -20 else 0))
        pose = ego_spawn_transform(Map(yaw_by_x=lambda x: .4 if x < -20 else 0), CARLA, site)
        self.assertEqual(pose.location.x, site['ego_start_xy_m'][0])
        self.assertEqual(pose.location.z, .5)
        self.assertAlmostEqual(pose.rotation.yaw, .4)
        with self.assertRaisesRegex(ValueError, 'differs from lane route'):
            ego_spawn_transform(Map(lane_by_x=lambda x: 2 if x < -20 else 1), CARLA, site)
        with self.assertRaisesRegex(ValueError, 'differs from lane route'):
            ego_spawn_transform(Map(y_by_x=lambda x: .5 if x < -20 else 0), CARLA, site)

    def test_static_cameras_follow_original_school_site(self):
        site = self.inspect()
        self.assertEqual(Cameras.placement('overview', site), (0, 0.0, 45, -90))
        shifted = json.loads(json.dumps(site))
        for marker in shifted['school_boundary_markers']:
            marker['location_xy_m'][0] += 420
        shifted['ego_start_xy_m'] = [385, 50]
        self.assertEqual(Cameras.placement('overview', shifted), (420, 50, 45, -90))
        self.assertEqual(Cameras.placement('approach', shifted), (390, 38, 12, -25))
        self.assertEqual(Cameras.placement('driver_reference', shifted), (0, 0, 2, 0))

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
