"""Source-gated delivery entrypoint checks before local CARLA adapter import."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RunnerEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        construction = json.loads((ROOT / "construction-two_cycles_failed_detection.json").read_text())
        for entry in construction["files"]:
            target = self.root / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry["content"])
        self.authority = self.root / "authority"
        self.authority.mkdir()
        self.site = {"cell_id": "C111125", "maneuver": "straight",
                     "device_kind": "official_traffic_control_device",
                     "ego_blueprint_class": "bicycle", "ego_blueprint_id": "vehicle.bicycle.test",
                     "rider_model_id": "walker.rider.test", "device_id": "signal.1",
                     "detector_id": "loop.1", "detector_controls_subject_signal": True,
                     "approach_lane_id": 1, "cross_lane_id": 2,
                     "stop_boundary_station_m": 1.0, "entry_station_m": 9.0,
                     "reviewed_original_site": True}
        packets = {
            "map": {k: self.site[k] for k in ("cell_id", "approach_lane_id", "cross_lane_id", "stop_boundary_station_m", "entry_station_m")},
            "device": {k: self.site[k] for k in ("device_id", "device_kind", "detector_id")},
            "detector": {"detector_id": "loop.1", "controls_device_id": "signal.1", "zone_lane_id": 1},
            "blueprint": {k: self.site[k] for k in ("ego_blueprint_id", "ego_blueprint_class", "rider_model_id")},
        }
        for name, data in packets.items():
            path = self.authority / (name + ".json")
            path.write_text(json.dumps(data, sort_keys=True) + "\n")
            self.site[name + "_ref"] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.site_path = self.authority / "site.json"
        self.site_path.write_text(json.dumps(self.site, sort_keys=True) + "\n")
        sys.path.insert(0, str(self.root))
        self.addCleanup(lambda: sys.path.remove(str(self.root)))
        spec = importlib.util.spec_from_file_location("c111125_test_runner", self.root / "runner.py")
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)

    def test_reviewed_native_shaped_source_reaches_adapter_boundary(self):
        case = self.runner.check(self.authority, self.site_path)
        self.assertTrue(case.endswith("__two_cycles_failed_detection"))
        with self.assertRaisesRegex(ValueError, "reviewed local CARLA site adapter missing"):
            self.runner.run_native(authority_root=self.authority, site_path=self.site_path,
                                   adapter_path=self.root / "missing_adapter.py",
                                   attempt_root=self.root / "attempt", host="127.0.0.1", port=2000)

    def test_missing_or_stale_source_rejected_before_adapter(self):
        (self.authority / "detector.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing source file"):
            self.runner.check(self.authority, self.site_path)
        (self.authority / "detector.json").write_text('{"detector_id":"wrong"}\n')
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            self.runner.check(self.authority, self.site_path)

    def test_unreviewed_site_rejected(self):
        site = dict(self.site, reviewed_original_site=False)
        self.site_path.write_text(json.dumps(site) + "\n")
        with self.assertRaisesRegex(ValueError, "reviewed original site authority missing"):
            self.runner.check(self.authority, self.site_path)


if __name__ == "__main__":
    unittest.main()
