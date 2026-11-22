"""Exercise both concrete engineering scenes and exact source rejection."""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
from shapely.geometry import box

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from runner import main
from uturn_control import bind_map, validate_scene


class OpeningCandidateTests(unittest.TestCase):
    def check(self, path):
        with patch.object(sys, "argv", ["runner.py", "--scene", str(path), "--check"]):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                main()
        return json.loads(out.getvalue())

    def test_exact_single_and_multiple_constructions(self):
        root = ET.parse(HERE / "candidate-median-opening.xodr").getroot()
        self.assertEqual([road.attrib["id"] for road in root.findall("road")], ["10", "20"])
        self.assertEqual([road.find("./lanes/laneSection/right/lane").attrib["type"]
                          for road in root.findall("road")], ["driving", "driving"])
        self.assertEqual(root.findall("road")[1].find("./lanes/laneSection/left/lane").attrib["id"],"1")
        paths = [HERE / "scene.json", HERE / "cases/opening_multiple/scene.json",
                 HERE / "cases/closed_divider/scene.json",
                 HERE / "cases/wrong_roadway/scene.json",
                 HERE / "cases/right_roadway_no_turn/scene.json",
                 HERE / "cases/crossover_candidate/scene.json",
                 HERE / "cases/intersection_candidate/scene.json"]
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(self.check(path)["static_construction_valid"])
        single, multiple, closed, wrong, no_turn, crossover, intersection = [
            json.loads(path.read_text()) for path in paths]
        self.assertEqual(single["context"], multiple["context"])
        self.assertEqual(single["context"], closed["context"])
        self.assertEqual(single["context"],wrong["context"])
        self.assertEqual(single["context"],no_turn["context"])
        self.assertTrue(box(*single["context"]["opening_bounds_xy_m"]).covers(box(-1,-2,3,2)))
        self.assertEqual(validate_scene(single)["reverse_segments"], [])
        self.assertEqual(validate_scene(multiple)["reverse_segments"], [4])
        self.assertGreater(validate_scene(closed)["minimum_divider_clearance_m"], 0)
        self.assertEqual(json.loads(paths[2].with_name("config.json").read_text())
                         ["physical_completion"]["criterion"],"travel_progress")
        self.assertEqual(wrong["destination_lane_id"],1)
        self.assertEqual(json.loads(paths[3].with_name("config.json").read_text())
                         ["physical_completion"]["criterion"],"travel_progress")
        self.assertEqual(no_turn["destination_road_id"],10)
        self.assertTrue(validate_scene(no_turn)["source_right_roadway_continuation"])
        self.assertEqual(crossover["context"]["crossing_kind"],"crossover_candidate")
        self.assertEqual(intersection["context"]["crossing_kind"],"intersection_candidate")
        self.assertNotEqual(crossover["context"]["map_source_sha256"],
                            intersection["context"]["map_source_sha256"])
        crossover_map=ET.parse(HERE/"candidate-crossover-candidate.xodr").getroot()
        intersection_map=ET.parse(HERE/"candidate-intersection-candidate.xodr").getroot()
        self.assertIn("30",[r.attrib["id"] for r in crossover_map.findall("road")])
        self.assertIn("31",[r.attrib["id"] for r in intersection_map.findall("road")])
        self.assertEqual(intersection_map.find("junction").attrib["id"],"1")
        self.assertEqual(json.loads((HERE/"candidate-authority-review.json").read_text())
                         ["public_authority_establishment"],"unverified")
        intrusion=copy.deepcopy(closed)
        intrusion["route_xy_m"][-1]=[-8,0]
        with self.assertRaisesRegex(ValueError,"does not stop clear"):
            validate_scene(intrusion)
        short_stop=copy.deepcopy(closed)
        short_stop["route_xy_m"][-1]=[-8,-2.5]
        with self.assertRaisesRegex(ValueError,"does not stop clear"):
            validate_scene(short_stop)
        right_lane=copy.deepcopy(wrong)
        right_lane["route_xy_m"][-1]=[-8,5.75]
        with self.assertRaisesRegex(ValueError,"destination"):
            validate_scene(right_lane)
        leaves_source=copy.deepcopy(no_turn)
        leaves_source["route_xy_m"][3]=[-6,-1]
        with self.assertRaisesRegex(ValueError,"leaves source"):
            validate_scene(leaves_source)

    def test_changed_map_bytes_rejected(self):
        scene = json.loads((HERE / "scene.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scene["reviewed_context_source"] = str(HERE / "candidate-reviewed-median.json")
            scene["authority_review_source"] = str(HERE / "candidate-authority-review.json")
            scene["map_source"] = str(root / "candidate-median-opening.xodr")
            (root / "candidate-median-opening.xodr").write_bytes(
                (HERE / "candidate-median-opening.xodr").read_bytes() + b" ")
            (root / "scene.json").write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "OpenDRIVE source hash"):
                self.check(root / "scene.json")

    def test_wrong_roadway_binds_opposite_driving_lane(self):
        scene=json.loads((HERE/"cases/wrong_roadway/scene.json").read_text())
        map_text=(HERE/"candidate-median-opening.xodr").read_text()
        class WorldMap:
            destination_lane=1
            def to_opendrive(self):return map_text
            def get_waypoint(self,location,project_to_road=False):
                road,lane=(10,-1) if location["y"]<0 else (20,self.destination_lane)
                return type("Waypoint",(),{"road_id":road,"lane_id":lane})()
        world=WorldMap()
        self.assertEqual(len(bind_map(world,scene,lambda x,y:{"x":x,"y":y})),2)
        world.destination_lane=-1
        with self.assertRaisesRegex(ValueError,"destination driving lane"):
            bind_map(world,scene,lambda x,y:{"x":x,"y":y})


if __name__ == "__main__":
    unittest.main()
