import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner
import native_officer


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
            invalid = dict(site, vehicle_route=[[-10, 0, 0], [-5, 0, 0]])
            path.write_text(json.dumps(invalid) + "\n")
            with self.assertRaisesRegex(ValueError, "route or stop-line geometry"):
                runner.preflight_sources(CASE, path, hashlib.sha256(path.read_bytes()).hexdigest(), None, None)
            path.write_text(json.dumps(site) + "\n")
            officer_case = next(row for row in PLAN["cases"] if row["officer_direction"] != "none")
            with self.assertRaisesRegex(ValueError, "authority source required"):
                runner.preflight_sources(officer_case, path, checksum, None, None)

    def test_exact_source_copied_before_session_mutation(self):
        site = {
            "source_kind": "original_local_native_site_inventory", "map_name": "reviewed-test-map",
            "jurisdiction_source": "reviewed citation", "governed_approach": "north",
            "stop_line": [[0, -1], [0, 1]], "vehicle_route": [[-10, 0, 0], [10, 0, 0]],
            "device_id": "device-1", "device_type": "signal",
            "device_authority_source": "reviewed-device", "vehicle_applicability_source": "reviewed-vehicle",
            "bike_blueprint_id": "vehicle.bicycle", "police_authority_source": "reviewed-police",
        }
        scratch = Path(".runtime-work").resolve()
        with tempfile.TemporaryDirectory(dir=scratch) as name:
            root = Path(name)
            source = root / "reviewed-site.json"
            source.write_text(json.dumps(site) + "\n")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            output = root / "attempt"
            output.mkdir()
            def fail_open(*_):
                self.assertEqual((output / "original-site.json").read_bytes(), source.read_bytes())
                raise RuntimeError("fake session refused")
            with patch.object(runner.importlib, "import_module",
                              return_value=SimpleNamespace(open_session=fail_open)):
                with self.assertRaisesRegex(RuntimeError, "fake session refused"):
                    runner.execute(ROOT, output, source, digest, None, None,
                                   "fake-adapter", "localhost", 2000)
            self.assertEqual(json.loads((output / "original-source-hashes.json").read_text())["site"], digest)

    def test_officer_fallback_requires_reviewed_alternate_sightline(self):
        officer_case = next(row for row in PLAN["cases"] if row["officer_direction"] == "proceed")
        site = {
            "source_kind": "original_local_native_site_inventory", "map_name": "reviewed-test-map",
            "jurisdiction_source": "reviewed citation", "governed_approach": "north",
            "stop_line": [[0, -1], [0, 1]], "vehicle_route": [[-10, 0, 0], [10, 0, 0]],
            "device_id": "device-1", "device_type": "signal",
            "device_authority_source": "reviewed-device", "vehicle_applicability_source": "reviewed-vehicle",
            "bike_blueprint_id": "vehicle.bicycle", "police_authority_source": "reviewed-police",
        }
        packet = {"source_kind": "original_local_officer_authority_and_gesture",
                  "map_name": "reviewed-test-map", "authority_source": "reviewed-police",
                  "officer_blueprint_id": "walker.officer", "gesture_asset_id": "reviewed-gesture",
                  "spawn_xyz": [0, 3, 0], "recipient_role": "selected_cycle_operator",
                  "recipient_route_sha256": native_officer.route_digest(site),
                  "command": "proceed", "start_frame": 10, "end_frame": 600,
                  "visible_camera_ids": ["overview", "approach"],
                  "pose_variant": "primary_visible_pose", "camera_sightline_source": "reviewed-sightline"}
        scratch = Path(".runtime-work").resolve()
        with tempfile.TemporaryDirectory(dir=scratch) as name:
            root = Path(name)
            site_path = root / "site.json"
            officer_path = root / "officer.json"
            site_path.write_text(json.dumps(site) + "\n")
            officer_path.write_text(json.dumps(packet) + "\n")
            site_sha = hashlib.sha256(site_path.read_bytes()).hexdigest()
            officer_sha = hashlib.sha256(officer_path.read_bytes()).hexdigest()
            self.assertEqual(runner.preflight_sources(officer_case, site_path, site_sha,
                             officer_path, officer_sha, "primary_visible_pose")["officer"], packet)
            with self.assertRaisesRegex(ValueError, "pose or camera sightline"):
                runner.preflight_sources(officer_case, site_path, site_sha,
                                         officer_path, officer_sha, "alternate_visible_pose")
            packet["pose_variant"] = "alternate_visible_pose"
            officer_path.write_text(json.dumps(packet) + "\n")
            officer_sha = hashlib.sha256(officer_path.read_bytes()).hexdigest()
            self.assertEqual(runner.preflight_sources(officer_case, site_path, site_sha,
                             officer_path, officer_sha, "alternate_visible_pose")["officer"], packet)

    def test_officer_source_binds_spawned_recipient_and_rejects_wrong_actor(self):
        officer_case = next(row for row in PLAN["cases"] if row["officer_direction"] == "proceed")
        site = {"source_kind": "original_local_native_site_inventory", "map_name": "reviewed-test-map",
                "jurisdiction_source": "reviewed citation", "governed_approach": "north",
                "stop_line": [[0, -1], [0, 1]], "vehicle_route": [[-10, 0, 0], [10, 0, 0]],
                "device_id": "device-1", "device_type": officer_case["device_type"],
                "device_authority_source": "reviewed-device", "vehicle_applicability_source": "reviewed-vehicle",
                "bike_blueprint_id": "vehicle.bicycle", "police_authority_source": "reviewed-police"}
        packet = {"source_kind": "original_local_officer_authority_and_gesture",
                  "map_name": site["map_name"], "authority_source": site["police_authority_source"],
                  "officer_blueprint_id": "walker.officer", "gesture_asset_id": "reviewed-gesture",
                  "spawn_xyz": [0, 3, 0], "recipient_role": "selected_cycle_operator",
                  "recipient_route_sha256": native_officer.route_digest(site),
                  "command": "proceed", "start_frame": 10, "end_frame": 600,
                  "visible_camera_ids": ["overview", "approach"],
                  "pose_variant": "primary_visible_pose", "camera_sightline_source": "reviewed-sightline"}
        scratch = Path(".runtime-work").resolve()
        with tempfile.TemporaryDirectory(dir=scratch) as name:
            root = Path(name)
            site_path, officer_path = root / "site.json", root / "officer.json"
            site_path.write_text(json.dumps(site) + "\n")
            officer_path.write_text(json.dumps(packet) + "\n")
            site_sha = hashlib.sha256(site_path.read_bytes()).hexdigest()
            officer_sha = hashlib.sha256(officer_path.read_bytes()).hexdigest()
            reviewed = runner.preflight_sources(officer_case, site_path, site_sha,
                                                officer_path, officer_sha, "primary_visible_pose")
            bike = SimpleNamespace(id=271828, is_alive=True)
            bound = native_officer.bind_recipient(reviewed["officer"], bike, reviewed["site"])
            actor = SimpleNamespace(id=314159, is_alive=True)
            observed = native_officer.read_command(actor, bound, 100,
                                                   lambda *_: "proceed", str(bike.id))
            self.assertEqual(observed["recipient_id"], "271828")
            self.assertNotIn("observed_recipient_bike_id", reviewed["officer"])
            with self.assertRaisesRegex(ValueError, "recipient mismatch"):
                native_officer.read_command(actor, bound, 100, lambda *_: "proceed", "wrong-bike")
            packet["recipient_route_sha256"] = "0" * 64
            officer_path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "recipient role or route"):
                runner.preflight_sources(officer_case, site_path, site_sha,
                                         officer_path, hashlib.sha256(officer_path.read_bytes()).hexdigest(),
                                         "primary_visible_pose")


if __name__ == "__main__":
    unittest.main()
