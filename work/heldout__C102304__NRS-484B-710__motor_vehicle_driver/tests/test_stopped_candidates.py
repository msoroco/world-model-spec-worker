"""Check that stopped-case fallback declarations change real Native knobs."""
import ast
import json
import sys
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.candidate_constructions import validate


def file_code(bundle, name):
    return next(item["content"] for item in bundle["files"] if item["path"] == name)


def keywords(source, name):
    calls = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == name]
    if len(calls) != 1:
        raise AssertionError("Expected one " + name + " call")
    return {item.arg: item.value for item in calls[0].keywords}


def approach_pose(source):
    assignment = next(node for node in ast.parse(source).body
                      if isinstance(node, ast.Assign) and
                      any(isinstance(target, ast.Name) and target.id == "CAMERAS"
                          for target in node.targets))
    return ast.literal_eval(assignment.value)["approach"]


class StoppedCandidateTests(unittest.TestCase):
    def test_route_gain_and_camera_alternatives(self):
        manifest = json.loads((FOLDER / "execution-manifest.json").read_text())
        entry = next(item for item in manifest["cases"]
                     if item["case_id"].endswith("__stopped_drive_to_450ft"))
        self.assertEqual(validate(FOLDER, entry, "NRS-484B-710", "C102304",
                                  required=True, candidate_count=4)["fallbacks"],
                         ["fallback1", "fallback2", "fallback3"])
        primary = json.loads((FOLDER / entry["construction"]).read_text())
        variants = {item["id"]: json.loads((FOLDER / item["construction"]).read_text())
                    for item in entry["candidates"]}
        route = keywords(file_code(primary, "runner.py"), "select_crest_route")
        denser = keywords(file_code(variants["fallback1"], "runner.py"), "select_crest_route")
        self.assertNotIn("step_m", route)
        self.assertEqual(ast.literal_eval(denser["step_m"]), 2.5)
        primary_control = keywords(file_code(primary, "runner.py"), "control_step")
        lower_control = keywords(file_code(variants["fallback2"], "runner.py"), "control_step")
        self.assertNotIn("gain", primary_control)
        self.assertEqual(ast.literal_eval(lower_control["gain"]), .28)
        self.assertEqual(ast.literal_eval(lower_control["speed_gain"]), .32)
        self.assertNotEqual(approach_pose(file_code(primary, "fire_camera_capture.py"))[0],
                            approach_pose(file_code(variants["fallback3"], "fire_camera_capture.py"))[0])
        for bundle in variants.values():
            config = json.loads(file_code(bundle, "config.json"))
            self.assertEqual(config["selected_case_id"], entry["case_id"])
            self.assertEqual(config["target_distance_ft"], 450)
            self.assertEqual(config["fire_branch"], "stopped_drive_to")


if __name__ == "__main__":
    unittest.main()
