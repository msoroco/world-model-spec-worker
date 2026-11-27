import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from audit_arm_cases import audit_case, audit_comparison
from finalize_sources import SOURCES
from runner import AID
from test_finalize_sources import SCRATCH, write_fixture


def case_fixture(root, method):
    write_fixture(root)
    rows = [json.loads(line) for line in (root / "rider_arm.jsonl").read_text().splitlines()]
    for frame, row in enumerate(rows):
        active = 100 <= frame < 140
        bones = row["bone_world_xyz_m"]
        right = active and method == "right_horizontal"
        left = active and method == "left_upward"
        row["requested_method"] = method if active else "none"
        bones["crl_foreArm__R"][1] = -.50 if right else -.30
        bones["crl_hand__R"][1] = -.80 if right else -.42
        bones["crl_foreArm__L"] = [0.0, .15 if left else .04,
                                    1.6 if left else 1.3]
        bones["crl_hand__L"] = [0.0, .3 if left else .08,
                                 1.9 if left else 1.2]
    (root / "rider_arm.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    seal_path = root / "capture-seal.json"
    seal = json.loads(seal_path.read_text())
    seal["sources"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                       for name in SOURCES}
    seal_path.write_text(json.dumps(seal) + "\n")


class TestIndependentArmAudit(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.temp.name)
        self.roots = {}
        for label, method in (("a", "right_horizontal"),
                              ("b", "none"), ("c", "left_upward")):
            path = self.root / label
            path.mkdir()
            case_fixture(path, method)
            self.roots[AID + "__probe_" + label] = path

    def tearDown(self):
        self.temp.cleanup()

    def test_all_exact_case_source_audits(self):
        for label, expected_right, expected_left in (("a", 40, 0),
                                                      ("b", 0, 0),
                                                      ("c", 0, 40)):
            report = audit_case(self.roots[AID + "__probe_" + label],
                                AID + "__probe_" + label, diagnostic_fixture=True)
            self.assertEqual(report["right_observed_frames_in_window"], expected_right)
            self.assertEqual(report["left_observed_frames_in_window"], expected_left)
            self.assertIsNone(report["legal_conclusion"])

    def test_comparison_fixed_conditions_and_missing_source_rejection(self):
        pair = [AID + "__probe_a", AID + "__probe_b"]
        report = audit_comparison(self.roots, pair, diagnostic_fixture=True)
        self.assertTrue(report["case_source_audits"][0]["source_join_passed"])
        context = self.roots[pair[1]] / "road_context.json"
        value = json.loads(context.read_text())
        value["roadway_polygon_xy_m"][0][0] -= 1
        context.write_text(json.dumps(value) + "\n")
        seal = self.roots[pair[1]] / "capture-seal.json"
        receipt = json.loads(seal.read_text())
        receipt["sources"]["road_context.json"] = hashlib.sha256(context.read_bytes()).hexdigest()
        seal.write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "fixed condition"):
            audit_comparison(self.roots, pair, diagnostic_fixture=True)
        (self.roots[pair[0]] / "rider_arm.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "sealed source"):
            audit_case(self.roots[pair[0]], pair[0], diagnostic_fixture=True)


if __name__ == "__main__":
    unittest.main()
