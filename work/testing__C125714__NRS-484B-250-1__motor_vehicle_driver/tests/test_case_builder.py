from pathlib import Path
import hashlib
import json
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from case_builder import ASSIGNMENT, config


def scene(reverse=False):
    return {"case_id": ASSIGNMENT + "__precedence", "capture_rate_hz": 20,
            "duration_s": 1, "reviewed_context_source": "reviewed-context.json",
            "reviewed_context_sha256": "source-hash",
            "crossing": {"crossing_id": "A-B", "map_source_sha256": "map-hash",
                         "bounds_xy_m": [-1,-1,1,1]},
            "ego_highway": "A", "other_highway": "B",
            "ego_route_xy_m": [[3,0],[0,0],[-3,0]] if reverse else [[-3,0],[0,0],[3,0]],
            "other_route_xy_m": [[0,-3],[0,0],[0,3]],
            "other_entered_first": True}


class CaseBuilderTests(unittest.TestCase):
    def test_departure_direction_and_polygon_derived_from_route(self):
        forward = config(scene())
        reverse = config(scene(True))
        self.assertEqual(forward["physical_completion"]["exit_axis"], 0)
        self.assertEqual(forward["physical_completion"]["exit_sign"], 1)
        self.assertEqual(reverse["physical_completion"]["exit_sign"], -1)
        self.assertEqual(forward["physical_completion"]["intersection_polygon_xy_m"],
                         [[-1,-1],[1,-1],[1,1],[-1,1]])
        self.assertEqual(forward["case"]["recording_description"]["channels"][0]["name"],
                         "ego_body_history")

    def test_wrong_assignment_identity_rejected(self):
        item = scene()
        item["case_id"] = "unassigned__precedence"
        with self.assertRaisesRegex(ValueError, "exact assignment"):
            config(item)

    def test_runner_check_rejects_stale_materialized_config(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            item = scene()
            (root / "reviewed-context.json").write_text(json.dumps({"crossing":item["crossing"]}))
            item["reviewed_context_sha256"] = hashlib.sha256(
                (root / "reviewed-context.json").read_bytes()).hexdigest()
            (root / "scene.json").write_text(json.dumps(item))
            expected = config(item)
            (root / "config.json").write_text(json.dumps(expected))
            command = [sys.executable, str(ROOT / "runner.py"), "--scene",
                       str(root / "scene.json"), "--check"]
            good = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertIn("static_construction_valid", good.stdout)
            expected["physical_completion"]["exit_sign"] = -1
            (root / "config.json").write_text(json.dumps(expected))
            stale = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("materialized exact config differs", stale.stderr)


if __name__ == "__main__": unittest.main()
