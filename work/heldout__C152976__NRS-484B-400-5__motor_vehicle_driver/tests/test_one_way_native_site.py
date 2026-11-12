import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('one_way_native_site', root/'one_way_native_site.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Rotation:
    def __init__(self, yaw): self.yaw = yaw
class Transform:
    def __init__(self, yaw): self.rotation = Rotation(yaw)
class Waypoint:
    def __init__(self, road, lane, s, yaw):
        self.road_id, self.lane_id, self.s = road, lane, s
        self.transform = Transform(yaw)
        self.lane_type = 'Driving'
        self.left = self.right = None
        self.follow = []
    def get_left_lane(self): return self.left
    def get_right_lane(self): return self.right
    def next(self, distance): return self.follow
class Map:
    def __init__(self):
        self.a = Waypoint(1, 1, 20, 90)
        self.j = Waypoint(3, 1, 0, 135)
        self.b = Waypoint(2, 1, 12, 180)
        self.a.follow = [self.j]
        self.j.follow = [self.b]
    def to_opendrive(self): return '<OpenDRIVE source="cpu fake"/>'
    def get_waypoint_xodr(self, road, lane, s):
        return {(1,1,20):self.a,(2,1,12):self.b}.get((road,lane,s))


class SurveyTest(unittest.TestCase):
    def site(self, path, world_map):
        obj = {'source_id':'survey-1',
               'opendrive_sha256':hashlib.sha256(world_map.to_opendrive().encode()).hexdigest(),
               'direction_sign_source':'Native sign inventory and pixel check pending',
               'approach':{'road_id':1,'lane_id':1,'s_m':20},
               'departure':{'road_id':2,'lane_id':1,'s_m':12}}
        Path(path).write_text(json.dumps(obj))
        return obj
    def test_connected_both_direction_readbacks(self):
        with TemporaryDirectory() as folder:
            world_map = Map(); path = Path(folder)/'site.json'
            self.site(path,world_map)
            result = m.survey(world_map,path)
            self.assertEqual(result['left_turn_heading_delta_deg'],90)
            self.assertEqual(result['opendrive_sha256'],hashlib.sha256(world_map.to_opendrive().encode()).hexdigest())
    def test_disconnected_wrong_turn_and_opposing_lane_rejected(self):
        with TemporaryDirectory() as folder:
            world_map = Map(); path = Path(folder)/'site.json'
            self.site(path,world_map)
            world_map.j.follow = []
            with self.assertRaisesRegex(ValueError,'does not connect'):m.survey(world_map,path)
            world_map.j.follow = [world_map.b]
            world_map.b.transform.rotation.yaw = 0
            with self.assertRaisesRegex(ValueError,'not a left turn'):m.survey(world_map,path)
            world_map.b.transform.rotation.yaw = 180
            world_map.a.left = Waypoint(1,-1,20,270)
            with self.assertRaisesRegex(ValueError,'opposing driving lane'):m.survey(world_map,path)
    def test_map_hash_and_sign_source_rejected(self):
        with TemporaryDirectory() as folder:
            world_map = Map(); path = Path(folder)/'site.json'
            site = self.site(path,world_map)
            site['opendrive_sha256'] = '0'*64
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError,'hash differs'):m.survey(world_map,path)
            site['opendrive_sha256'] = hashlib.sha256(world_map.to_opendrive().encode()).hexdigest()
            site['direction_sign_source'] = ''
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError,'sign source absent'):m.survey(world_map,path)


if __name__ == '__main__': unittest.main()
