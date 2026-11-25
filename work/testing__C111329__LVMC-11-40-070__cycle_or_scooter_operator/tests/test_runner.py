import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
CASE = PLAN["cases"][0]


class RunnerTests(unittest.TestCase):
    def test_missing_reviewed_sources_before_adapter_import(self):
        with patch.object(runner.importlib, "import_module") as importer:
            with self.assertRaises(FileNotFoundError):
                runner.execute(ROOT, Path(".runtime-work"), Path("/missing/original-site.json"),
                               "0" * 64, None, None, "adapter", "localhost", 2000)
        importer.assert_not_called()

    def test_case_identity_and_source_gate(self):
        self.assertEqual(runner.check(ROOT)["case_id"], CASE["case_id"])

    def test_site_and_officer_source_preflight(self):
        site = {
            "source_kind": "original_local_native_site_inventory", "map_name": "reviewed-test-map",
            "jurisdiction_source": "reviewed citation", "governed_approach": "north",
            "stop_line": [[0, -1], [0, 1]], "vehicle_route": [[-10, 0, 0], [10, 0, 0]],
            "device_id": "device-1", "device_type": "signal",
            "device_authority_source": "reviewed-device", "vehicle_applicability_source": "reviewed-vehicle",
            "bike_blueprint_id": "vehicle.bicycle", "police_authority_source": "reviewed-police",
        }
        temp_parent = Path(".runtime-work").resolve()
        temp_parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_parent) as name:
            path = Path(name) / "original-site.json"
            path.write_text(json.dumps(site) + "\n")
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(runner.preflight_sources(CASE, path, checksum, None, None)["site"], site)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                runner.preflight_sources(CASE, path, "0" * 64, None, None)
            officer_case = next(row for row in PLAN["cases"] if row["officer_direction"] != "none")
            with self.assertRaisesRegex(ValueError, "authority source required"):
                runner.preflight_sources(officer_case, path, checksum, None, None)


if __name__ == "__main__":
    unittest.main()
