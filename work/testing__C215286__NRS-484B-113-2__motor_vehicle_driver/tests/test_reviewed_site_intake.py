"""Synthetic packets test only the intake contract, never actual site review."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reviewed_site_intake", PACKAGE / "cases/reviewed_site_intake.py")
INTAKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INTAKE)
INSTALL_SPEC = importlib.util.spec_from_file_location("reviewed_site_install", PACKAGE / "reviewed_site_install.py")
import sys
sys.modules["reviewed_site_intake"] = INTAKE
INSTALL = importlib.util.module_from_spec(INSTALL_SPEC)
INSTALL_SPEC.loader.exec_module(INSTALL)
import reverse_alternative_capture as ALTERNATIVE_CAPTURE


class ReviewedSiteIntakeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in INTAKE.NAMES:
            shutil.copyfile(PACKAGE / name, self.root / name)
        for keys in INTAKE.SOURCE_KEYS.values():
            for name in keys:
                for packet in INTAKE.NAMES:
                    row = json.loads((PACKAGE / packet).read_text()).get(name)
                    if row:
                        shutil.copyfile(PACKAGE / row["path"], self.root / row["path"])

    def _packet(self, name, changes):
        path = self.root / name
        packet = json.loads(path.read_text())
        packet.update(changes)
        path.write_text(json.dumps(packet) + "\n")

    def _reviewed_fixture(self):
        for name in INTAKE.NAMES:
            fields = ({"reviewer": "fixture reviewer", "district_review_basis": "fixture declaration",
                       "crosswalk_review_basis": "fixture declaration", "camera_review_basis": "fixture declaration"}
                      if name == "site_packet.json" else
                      {"site_reviewer": "fixture reviewer", "site_review_basis": "fixture declaration",
                       "camera_review_basis": "fixture declaration"})
            self._packet(name, {"site_review_status": "reviewed_native_site",
                                "native_map_id": "FixtureMap", **fields})

    def test_diagnostic_bundle_rejected(self):
        with self.assertRaisesRegex(ValueError, "Original Native site review required"):
            INTAKE.check(self.root)

    def test_structural_fixture_checks_sources_and_pair_identity(self):
        self._reviewed_fixture()
        receipt = INTAKE.check(self.root)
        self.assertEqual(receipt["status"], "structural_only")
        self.assertFalse(receipt["actual_native_geometry_verified"])
        (self.root / "district.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "Changed source: district_source"):
            INTAKE.check(self.root)
        shutil.copyfile(PACKAGE / "district.txt", self.root / "district.txt")
        self._packet("intersection_stop_site.json", {"road_id": 999})
        with self.assertRaisesRegex(ValueError, "Selected pair map or road identity differs"):
            INTAKE.check(self.root)

    def test_install_reviewed_bundle_into_materialized_attempt(self):
        self._reviewed_fixture()
        attempt = self.root / "attempt"
        attempt.mkdir()
        (attempt / "construction.json").write_text("{}\n")
        (attempt / "site_packet.json").write_text((PACKAGE / "site_packet.json").read_text())
        case = PACKAGE.name + "__reverse_over_crosswalk"
        with patch.dict("os.environ", {"C215286_REVIEW_BUNDLE": str(self.root)}):
            receipt = INSTALL.install(attempt, case)
        self.assertEqual(receipt["intake_status"], "structural_only")
        self.assertFalse(receipt["physical_acceptance_claimed"])
        self.assertEqual((attempt / "site_packet.json").read_bytes(),
                         (self.root / "site_packet.json").read_bytes())
        self.assertEqual((attempt / "district.txt").read_bytes(),
                         (self.root / "district.txt").read_bytes())

    def test_install_rejects_diagnostic_and_changed_source_before_write(self):
        attempt = self.root / "attempt"
        attempt.mkdir()
        (attempt / "construction.json").write_text("{}\n")
        original = (PACKAGE / "site_packet.json").read_text()
        (attempt / "site_packet.json").write_text(original)
        case = PACKAGE.name + "__reverse_over_crosswalk"
        with patch.dict("os.environ", {"C215286_REVIEW_BUNDLE": str(self.root)}):
            with self.assertRaisesRegex(ValueError, "Original Native site review required"):
                INSTALL.install(attempt, case)
            self._reviewed_fixture()
            (self.root / "district.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "Changed source: district_source"):
                INSTALL.install(attempt, case)
        self.assertEqual((attempt / "site_packet.json").read_text(), original)

    def test_install_alternative_requires_selected_blueprint(self):
        self._reviewed_fixture()
        attempt = self.root / "attempt"
        templates = attempt / "site_templates"
        templates.mkdir(parents=True)
        (attempt / "construction.json").write_text("{}\n")
        name = "intersection_site.json"
        original = (PACKAGE / name).read_text()
        (templates / name).write_text(original)
        case = PACKAGE.name + "__reverse_into_intersection"
        with patch.dict("os.environ", {"C215286_REVIEW_BUNDLE": str(self.root)}):
            receipt = INSTALL.install(attempt, case)
            self.assertEqual(receipt["site_packet"], name)
            self.assertEqual((attempt / name).read_bytes(), (self.root / name).read_bytes())
            ALTERNATIVE_CAPTURE._publish_site_sources(attempt, json.loads((attempt / name).read_text()), case)
            self._packet(name, {"vehicle_blueprint_id": "vehicle.other"})
            with self.assertRaisesRegex(ValueError, "selected candidate blueprint"):
                INSTALL.install(attempt, case)


if __name__ == "__main__":
    unittest.main()
