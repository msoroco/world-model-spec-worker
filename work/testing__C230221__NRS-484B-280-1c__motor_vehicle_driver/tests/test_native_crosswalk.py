"""Exercise Native map and sidewalk source readback for both crossing kinds."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import Recorder, inspect_crosswalk, pedestrian_destination


class Carla:
    class LaneType:
        Driving = 'driving'
        Sidewalk = 'sidewalk'

    @staticmethod
    def Location(x, y, z):
        return SimpleNamespace(x=x, y=y, z=z)


class Waypoint:
    def __init__(self, road_id, lane_type, x, y, junction, width=1.8):
        self.road_id, self.lane_type, self.is_junction = road_id, lane_type, junction
        self.lane_width = width
        self.transform = SimpleNamespace(location=SimpleNamespace(x=x, y=y, z=0.0))


class Map:
    def __init__(self, kind, missing_sidewalk=False, remote_marking=False):
        self.kind, self.missing_sidewalk, self.remote_marking = kind, missing_sidewalk, remote_marking

    def to_opendrive(self):
        marker = '<objects><object id="mark-1" type="crosswalk"/></objects>' if self.kind == 'marked' or self.remote_marking else '<objects/>'
        if self.remote_marking:
            return '<OpenDRIVE><road id="main">' + marker + '</road><road id="crossing"/></OpenDRIVE>'
        return '<OpenDRIVE><road id="main"/><road id="crossing">' + marker + '</road></OpenDRIVE>'

    def get_waypoint(self, location, project_to_road, lane_type):
        if lane_type == Carla.LaneType.Sidewalk:
            if self.missing_sidewalk:
                return None
            return Waypoint('crossing', lane_type, location.x, location.y, True)
        if location.x < -10:
            return Waypoint('main', lane_type, location.x, location.y, False)
        return Waypoint('crossing', lane_type, location.x, location.y, True)

    def get_crosswalks(self):
        return [SimpleNamespace(x=x, y=y) for x,y in ((-1,-4),(1,-4),(1,4),(-1,4))] if self.kind == 'marked' else []


class World:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_map(self):
        return self.mapping


class NativeCrosswalkReadbackTests(unittest.TestCase):
    def scene(self, kind):
        return {'case_id': ROOT.name + '__' + kind + '_crosswalk', 'crosswalk_kind': kind,
                'ego_start_xy_m': [-30,0], 'ego_end_xy_m': [20,0],
                'pedestrian_start_xy_m': [0,-5], 'pedestrian_end_xy_m': [0,5]}

    def test_pedestrian_motion_uses_actual_route_length(self):
        scene = dict(self.scene('marked'), rate_hz=20,
                     pedestrian_target_speed_mps=0.3)
        first = pedestrian_destination(scene, 0)
        after_one_second = pedestrian_destination(scene, 19)
        self.assertAlmostEqual(first[1], -4.985)
        self.assertAlmostEqual(after_one_second[1], -4.7)
        self.assertAlmostEqual(pedestrian_destination(scene, 599)[1], 4.0)
        with self.assertRaisesRegex(ValueError, 'invalid original pedestrian route'):
            pedestrian_destination(dict(scene, pedestrian_end_xy_m=[0, -5]), 0)

    def test_both_crossing_kinds_construct_from_original_map(self):
        for kind in ('marked','unmarked'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as temp:
                site = inspect_crosswalk(World(Map(kind)), Carla, self.scene(kind), Path(temp))
                self.assertEqual(site['crosswalk_kind'], kind)
                self.assertEqual(site['intersecting_road_ids'], ['main','crossing'])
                self.assertTrue((Path(temp)/'map.xodr').is_file())
                self.assertEqual(json.loads((Path(temp)/'crosswalk-site.json').read_text()), site)

    def test_missing_opposing_sidewalk_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as temp:
            with self.assertRaisesRegex(ValueError, 'lane waypoint'):
                inspect_crosswalk(World(Map('unmarked', True)), Carla,
                                  self.scene('unmarked'), Path(temp))

    def test_marked_kind_requires_original_marking(self):
        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as temp:
            with self.assertRaisesRegex(ValueError, 'marking'):
                inspect_crosswalk(World(Map('unmarked')), Carla,
                                  self.scene('marked'), Path(temp))

    def test_marked_kind_rejects_only_remote_road_marking(self):
        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as temp:
            with self.assertRaisesRegex(ValueError, 'crossing road'):
                inspect_crosswalk(World(Map('marked', remote_marking=True)), Carla,
                                  self.scene('marked'), Path(temp))

    def test_unmarked_kind_allows_remote_road_marking(self):
        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as temp:
            site = inspect_crosswalk(World(Map('unmarked', remote_marking=True)), Carla,
                                     self.scene('unmarked'), Path(temp))
            self.assertIsNone(site['marking_object_id'])
            self.assertEqual(site['crossing_road_id'], 'crossing')

    def test_original_recorder_lifecycle_and_fresh_source(self):
        class Client:
            def __init__(self):
                self.calls = []

            def start_recorder(self, path, additional_data):
                self.calls.append(('start', path, additional_data))
                Path(path).write_text('original CARLA recording')

            def stop_recorder(self):
                self.calls.append(('stop',))

        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as temp:
            path = Path(temp) / 'carla_recorder.log'
            client = Client()
            recorder = Recorder(client, path)
            recorder.start()
            self.assertTrue(recorder.active)
            self.assertEqual(client.calls, [('start', str(path), True)])
            recorder.stop()
            recorder.stop()
            self.assertFalse(recorder.active)
            self.assertEqual(client.calls[-1], ('stop',))
            self.assertEqual(len(client.calls), 2)
            with self.assertRaisesRegex(ValueError, 'fresh'):
                recorder.start()

    def test_recorder_failure_cleanup_and_missing_output_rejected(self):
        class Client:
            def __init__(self):
                self.stopped = False

            def start_recorder(self, path, additional_data):
                pass

            def stop_recorder(self):
                self.stopped = True

        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as temp:
            client = Client()
            recorder = Recorder(client, Path(temp) / 'carla_recorder.log')
            try:
                recorder.start()
                raise RuntimeError('capture failed')
            except RuntimeError:
                pass
            finally:
                with self.assertRaisesRegex(RuntimeError, 'missing or empty'):
                    recorder.stop()
            self.assertTrue(client.stopped)
            self.assertFalse(recorder.active)


if __name__ == '__main__':
    unittest.main()
