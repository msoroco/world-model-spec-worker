"""Check that the three declared fallbacks alter their stated Native knobs."""
import ast
import json
import sys
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))

from worker_exchange.candidate_constructions import validate


def code(construction, name):
    return next(item["content"] for item in construction["files"]
                if item["path"] == name)


def call_keywords(source, function):
    calls = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == function]
    if len(calls) != 1:
        raise AssertionError("Expected one " + function + " call")
    return {item.arg: ast.literal_eval(item.value) for item in calls[0].keywords
            if item.arg != "carla_module"}


def camera_pose(source):
    tree = ast.parse(source)
    value = next(node.value for node in tree.body
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "CAMERAS"
                         for target in node.targets))
    return ast.literal_eval(value)["approach"]


class FirstCandidateTests(unittest.TestCase):
    def test_distinct_route_controller_and_camera_changes(self):
        manifest = json.loads((FOLDER / "execution-manifest.json").read_text())
        entry = manifest["cases"][0]
        self.assertEqual(validate(FOLDER, entry, "NRS-484B-710", "C102304",
                                  required=True, candidate_count=4)["fallbacks"],
                         ["fallback1", "fallback2", "fallback3"])
        primary = json.loads((FOLDER / entry["construction"]).read_text())
        fallbacks = {item["id"]: json.loads((FOLDER / item["construction"]).read_text())
                     for item in entry["candidates"]}
        route = "select_crest_route"
        self.assertNotIn("step_m", call_keywords(code(primary, "runner.py"), route))
        self.assertEqual(call_keywords(code(fallbacks["fallback1"], "runner.py"), route)["step_m"], 2.5)
        control = "control_step"
        self.assertNotIn("gain", call_keywords(code(primary, "runner.py"), control))
        self.assertEqual(call_keywords(code(fallbacks["fallback2"], "runner.py"), control)["gain"], .12)
        self.assertEqual(call_keywords(code(fallbacks["fallback2"], "runner.py"), control)["speed_gain"], .22)
        original_pose = camera_pose(code(primary, "fire_camera_capture.py"))
        alternate_pose = camera_pose(code(fallbacks["fallback3"], "fire_camera_capture.py"))
        self.assertNotEqual(original_pose[0], alternate_pose[0])
        self.assertEqual(original_pose[2:], alternate_pose[2:])
        for item in fallbacks.values():
            config = json.loads(code(item, "config.json"))
            self.assertEqual(config["selected_case_id"], entry["case_id"])
            self.assertEqual(config["target_distance_ft"], 500)


if __name__ == "__main__":
    unittest.main()
