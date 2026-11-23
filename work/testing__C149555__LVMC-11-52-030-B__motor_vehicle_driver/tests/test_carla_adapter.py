import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("carla_adapter", ROOT / "carla_adapter.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Map:
    name = "ReviewedTown"

    def __init__(self, opposite=False):
        self.xml = '<OpenDRIVE><road id="2"><lanes><laneSection><right><lane id="-1" type="driving"/></right>' + ('<left><lane id="1" type="driving"/></left>' if opposite else '') + '</laneSection></lanes></road></OpenDRIVE>'

    def to_opendrive(self):
        return self.xml

    def get_waypoint_xodr(self, road_id, lane_id, station):
        return type("Waypoint", (), {"road_id": road_id, "lane_id": lane_id})()


class World:
    def __init__(self, m):
        self.m = m

    def get_map(self):
        return self.m


class NativeAdapterTests(unittest.TestCase):
    def test_native_map_and_one_way_are_checked_before_spawn(self):
        m = Map()
        s = {"native_map_name": "ReviewedTown", "approach_station_m": 5}
        adapter = module.NativeCarlaAdapter(World(m), s, {}, carla_module=object())
        adapter.assert_native_map(hashlib.sha256(m.xml.encode()).hexdigest())
        adapter.assert_one_way_lane(2, -1)
        with self.assertRaisesRegex(module.SourceError, "OpenDRIVE map seal"):
            adapter.assert_native_map("bad")
        other = module.NativeCarlaAdapter(World(Map(opposite=True)), s, {}, carla_module=object())
        with self.assertRaisesRegex(module.SourceError, "one-way"):
            other.assert_one_way_lane(2, -1)

    def test_yellow_curb_requires_sealed_original_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "curb.json"
            observation = {"map_name": "ReviewedTown", "color": "yellow", "start_station_m": 20, "end_station_m": 40, "independent_pixel_review": True}
            p.write_text(json.dumps(observation), encoding="utf-8")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            adapter = module.NativeCarlaAdapter(World(Map()), {"curb_observation_path": str(p)}, {}, carla_module=object())
            adapter.assert_yellow_curb({"start_station_m": 20, "end_station_m": 40}, digest)
            observation["independent_pixel_review"] = False
            p.write_text(json.dumps(observation), encoding="utf-8")
            with self.assertRaisesRegex(module.SourceError, "stale original source"):
                adapter.assert_yellow_curb({"start_station_m": 20, "end_station_m": 40}, digest)


if __name__ == "__main__":
    unittest.main()
