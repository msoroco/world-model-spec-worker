import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewed_site import SITE_ROLES, read_reviewed_site
from yield_view import CASES


class ReviewedSiteTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = CASES[0]
        site = {
            "cell_id": "C157964", "actor": "motor_vehicle_driver",
            "yield_sign_present": True, "stop_line_present": False,
            "near_crosswalk_present": False, "officer_controls": False,
            "signal_controls": False, "nearest_view_station_m": 0,
            "physical_reference_station_m": 2,
            "route_xy": [[-20, 0], [-4, 0], [4, 0]],
            "through_spawn_xy": [0, -20],
            "camera_dimensions": {view: [2, 2] for view in
                                  ("overview", "approach", "reference_corner", "driver_reference")},
        }
        refs = {}
        for role in SITE_ROLES:
            path = self.root / (role + ".json")
            path.write_text(json.dumps({"role": role, "reviewed": True}) + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            refs[role] = {"path": path.name, "sha256": digest}
            site[role + "_source_sha256"] = digest
        self.packet = {
            "format": "c157964-reviewed-yield-site-v1",
            "provenance": "reviewed_original", "case_id": self.case.case_id,
            "site": site, "sources": refs,
        }
        self.packet_path = self.root / "packet.json"
        self.save()

    def save(self):
        self.packet_path.write_text(json.dumps(self.packet, sort_keys=True) + "\n")

    def test_exact_source_packet(self):
        site, digest = read_reviewed_site(self.packet_path, self.root, self.case)
        self.assertEqual(site["physical_reference_station_m"], 2)
        self.assertEqual(digest, hashlib.sha256(self.packet_path.read_bytes()).hexdigest())

    def test_changed_source_and_diagnostic_rejected(self):
        (self.root / "yield_sign.json").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "bytes changed: yield_sign"):
            read_reviewed_site(self.packet_path, self.root, self.case)
        (self.root / "yield_sign.json").write_text(json.dumps({"role": "yield_sign", "reviewed": True}) + "\n")
        self.packet["provenance"] = "diagnostic_fixture"
        self.save()
        with self.assertRaisesRegex(ValueError, "diagnostic site"):
            read_reviewed_site(self.packet_path, self.root, self.case)

    def test_case_and_path_escape_rejected(self):
        self.packet["case_id"] = CASES[1].case_id
        self.save()
        with self.assertRaisesRegex(ValueError, "case differs"):
            read_reviewed_site(self.packet_path, self.root, self.case)
        self.packet["case_id"] = self.case.case_id
        self.packet["sources"]["yield_sign"]["path"] = "../outside.json"
        self.save()
        with self.assertRaisesRegex(ValueError, "escapes or is missing"):
            read_reviewed_site(self.packet_path, self.root, self.case)

    def test_missing_role_rejected(self):
        del self.packet["sources"]["sight_observation"]
        self.save()
        with self.assertRaisesRegex(ValueError, "source roles differ"):
            read_reviewed_site(self.packet_path, self.root, self.case)


if __name__ == "__main__":
    unittest.main()
