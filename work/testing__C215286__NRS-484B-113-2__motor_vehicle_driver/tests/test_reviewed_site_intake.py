"""Synthetic packets test only the intake contract, never actual site review."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reviewed_site_intake", PACKAGE / "cases/reviewed_site_intake.py")
INTAKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INTAKE)


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

    def test_diagnostic_bundle_rejected(self):
        with self.assertRaisesRegex(ValueError, "Original Native site review required"):
            INTAKE.check(self.root)

    def test_structural_fixture_checks_sources_and_pair_identity(self):
        for name in INTAKE.NAMES:
            fields = ({"reviewer": "fixture reviewer", "district_review_basis": "fixture declaration",
                       "crosswalk_review_basis": "fixture declaration", "camera_review_basis": "fixture declaration"}
                      if name == "site_packet.json" else
                      {"site_reviewer": "fixture reviewer", "site_review_basis": "fixture declaration",
                       "camera_review_basis": "fixture declaration"})
            self._packet(name, {"site_review_status": "reviewed_native_site",
                                "native_map_id": "FixtureMap", **fields})
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


if __name__ == "__main__":
    unittest.main()
