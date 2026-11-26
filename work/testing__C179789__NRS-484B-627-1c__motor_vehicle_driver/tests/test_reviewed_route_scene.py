import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alternate_route import CASES
from reviewed_route_scene import plan
from test_alternate_route import scene


ASSIGNMENT = "testing__C179789__NRS-484B-627-1c__motor_vehicle_driver"


def write(path, value):
    path.write_text(value if isinstance(value, str) else json.dumps(value))
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class ReviewedRouteSceneTest(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ["TMPDIR"])
        parent.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def packet(self, case):
        map_ref = write(self.root / "map.xodr", "<OpenDRIVE><road id='1'/></OpenDRIVE>")
        restriction_ref = write(self.root / "restrictions.json", {
            "alternate_restriction_state": "open" if case.alternate_declared else "restricted",
            "journey_destination": "diagnostic destination", "restriction_source": "fixture review"})
        x = {"reviewed_original_site": True, "diagnostic_fixture": False,
             "map_ref": map_ref, "restriction_ref": restriction_ref,
             "highway_legal_review": {"source": "fixture review"},
             "controlled_access_legal_review": {"source": "fixture review",
                                                  "declared": case.controlled_access},
             "scene": dict(scene(case), reviewed_alternate_road_ids=[7]), "camera_profiles": {name: {
                 "pose": {"x": 0, "y": 0, "z": 3, "pitch": 0, "yaw": 0, "roll": 0},
                 "width": 1920 if name == "overview" else 1280,
                 "height": 1080 if name == "overview" else 720, "fov_deg": 90}
                 for name in ("overview", "approach", "reference_corner", "driver_reference")}}
        return write(self.root / "site.json", x)

    def test_four_exact_plans_retain_source_and_unresolved_judgment(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                ref = self.packet(case)
                got = plan(self.root, ref, ASSIGNMENT + "__" + case.case_id)
                self.assertEqual(got["frames"], 900)
                self.assertEqual(got["scene"]["alternate_declared"], case.alternate_declared)
                self.assertIsNone(got["possible_route_judgment"])

    def test_rejects_stale_site_and_unreviewed_classification(self):
        ref = self.packet(CASES[0])
        (self.root / "site.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            plan(self.root, ref, ASSIGNMENT + "__alternate_selected")
        ref = self.packet(CASES[0])
        site_path = self.root / "site.json"
        data = json.loads(site_path.read_text())
        data["controlled_access_legal_review"] = {}
        ref = write(site_path, data)
        with self.assertRaisesRegex(ValueError, "classification source missing"):
            plan(self.root, ref, ASSIGNMENT + "__alternate_selected")

    def test_rejects_restriction_and_wrong_case(self):
        ref = self.packet(CASES[0])
        write(self.root / "restrictions.json", {
            "alternate_restriction_state": "restricted", "journey_destination": "fixture",
            "restriction_source": "fixture"})
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            plan(self.root, ref, ASSIGNMENT + "__alternate_selected")
        with self.assertRaisesRegex(ValueError, "unselected exact"):
            plan(self.root, ref, ASSIGNMENT + "__another_case")


if __name__ == "__main__":
    unittest.main()
