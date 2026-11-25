"""Source-shaped synthetic pair fixtures; no real source review is claimed."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from cycle_lane_comparison import audit_pairs
from cycle_lane_finalize import run as finalize
import test_cycle_lane_original as fixture_module
from cycle_lane_intersection import ASSIGNMENT


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.OriginalAuditTests()
        self.fixture.setUp()
        scratch = Path.cwd() / ".runtime-work" / "c230223-unit"
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)
        self.attempts = {}
        self.reviews = {}
        variants = (
            ("cycle_lane_through_intersection", "test_route", True, "does_not_apply"),
            ("cycle_lane_before_intersection_only", "before_route", False, "does_not_apply"),
            ("ordinary_lane_through_intersection", "ordinary_route", False, "does_not_apply"),
            ("cycle_lane_exception_unresolved", "test_route", True, "unresolved"),
        )
        for suffix, route, overlap, status in variants:
            case_id = ASSIGNMENT + "__" + suffix
            target = self.root / suffix
            shutil.copytree(self.fixture.root, target)
            seal = json.loads((target / "attempt-source.json").read_text())
            seal["case_id"] = case_id
            seal["route_candidate_id"] = route
            rows = json.loads((target / "history.json").read_text())
            for row in rows:
                row["ego_body_in_designated_cycle_lane"] = overlap and row["ego_body_in_designated_cycle_lane"]
                row["ego_body_polygon"] = fixture_module.body_polygon(
                    row["ego_body_in_intersection"], row["ego_body_in_designated_cycle_lane"])
            seal["history"] = fixture_module.write(target, "history.json", rows)
            exception = json.loads((target / "exception.json").read_text())
            exception["status"] = status
            seal["subsection_3"] = fixture_module.write(target, "exception.json", exception)
            fixture_module.write(target, "attempt-source.json", seal)
            self.attempts[case_id] = target
            self.reviews[case_id] = {"site": seal["site"]["sha256"],
                                      "vehicle": seal["vehicle"]["sha256"],
                                      "subsection_3": seal["subsection_3"]["sha256"]}

    def tearDown(self):
        self.temp.cleanup()
        self.fixture.tearDown()

    def test_three_exact_comparisons(self):
        result = audit_pairs(self.attempts, self.reviews)
        self.assertEqual(len(result["comparisons"]), 3)
        self.assertTrue(all(pair["fixed_source_verified"] for pair in result["comparisons"]))
        self.assertIsNone(result["legal_verdict"])

    def test_missing_attempt_rejected(self):
        self.attempts.pop(ASSIGNMENT + "__ordinary_lane_through_intersection")
        with self.assertRaisesRegex(ValueError, "all four"):
            audit_pairs(self.attempts, self.reviews)

    def test_changed_fixed_site_rejected(self):
        target = self.attempts[ASSIGNMENT + "__ordinary_lane_through_intersection"]
        seal = json.loads((target / "attempt-source.json").read_text())
        site = json.loads((target / "site.json").read_text())
        site["map_id"] = "changed-test-map"
        seal["site"] = fixture_module.write(target, "site.json", site)
        fixture_module.write(target, "attempt-source.json", seal)
        self.reviews[seal["case_id"]]["site"] = seal["site"]["sha256"]
        with self.assertRaisesRegex(ValueError, "fixed source conditions changed"):
            audit_pairs(self.attempts, self.reviews)

    def test_missing_overlap_rejected(self):
        target = self.attempts[ASSIGNMENT + "__cycle_lane_through_intersection"]
        seal = json.loads((target / "attempt-source.json").read_text())
        rows = json.loads((target / "history.json").read_text())
        for row in rows:
            row["ego_body_in_designated_cycle_lane"] = False
            row["ego_body_polygon"] = fixture_module.body_polygon(
                row["ego_body_in_intersection"], False)
        seal["history"] = fixture_module.write(target, "history.json", rows)
        fixture_module.write(target, "attempt-source.json", seal)
        with self.assertRaisesRegex(ValueError, "controlled overlap observations missing"):
            audit_pairs(self.attempts, self.reviews)

    def test_saved_only_finalizer_on_synthetic_four_case_video(self):
        video = self.root / "synthetic.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=blue:size=64x64:rate=20:duration=45",
                        "-c:v", "mpeg4", "-q:v", "2", "-an", str(video)],
                       check=True, capture_output=True, timeout=60)
        for target in self.attempts.values():
            seal = json.loads((target / "attempt-source.json").read_text())
            for view, reference in seal["cameras"].items():
                camera = target / reference["path"]
                camera.write_bytes(video.read_bytes())
                reference["sha256"] = hashlib.sha256(camera.read_bytes()).hexdigest()
            fixture_module.write(target, "attempt-source.json", seal)
        review = self.root / "review.json"
        review.write_text(json.dumps({"attempts": {case: str(path) for case, path in self.attempts.items()},
                                      "reviews": self.reviews}))
        output = self.root / "finalized.json"
        result = finalize(review, output)
        self.assertEqual(len(result["deliveries"]), 4)
        self.assertEqual(len(result["comparisons"]), 3)
        self.assertTrue(output.exists())
        self.assertFalse(result["physical_acceptance_claimed"])
