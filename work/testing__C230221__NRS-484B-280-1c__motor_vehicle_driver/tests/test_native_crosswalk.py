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
from native_capture import inspect_crosswalk


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
    def __init__(self, kind, missing_sidewalk=False):
        self.kind, self.missing_sidewalk = kind, missing_sidewalk

    def to_opendrive(self):
        marker = '<objects><object id="mark-1" type="crosswalk"/></objects>' if self.kind == 'marked' else '<objects/>'
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


if __name__ == '__main__':
    unittest.main()
