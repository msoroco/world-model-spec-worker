"""Exercise the Native runner closure without importing CARLA or runtime code."""
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import capture_original


class RunnerCaptureClosureTests(unittest.TestCase):
    def _modules(self, events, *, fail=False):
        world = NS(apply_settings=lambda settings: events.append("settings"))
        client = NS(set_timeout=lambda value: None, get_world=lambda: world)
        carla = ModuleType("carla")
        carla.Client = lambda host, port: client
        carla.VehicleControl = object
        carla.WalkerControl = object
        carla.Vector3D = object
        carla.Transform = lambda *args: args
        carla.Location = lambda *args: args
        carla.Rotation = lambda *args: args
        worker = ModuleType("worker_exchange")
        worker.__path__ = []
        native = ModuleType("worker_exchange.native_output")
        native.seal_capture = lambda *args, **kw: (events.append("seal"), {"format": "worker-sealed-capture"})[1]
        restoration = ModuleType("worker_exchange.world_restore")
        restoration.snapshot = lambda client: {"settings": NS(synchronous_mode=False,
            no_rendering_mode=False, fixed_delta_seconds=None)}
        restoration.restore = lambda client, saved: (events.append("restore"), {"restored": True})[1]
        return {"carla": carla, "worker_exchange": worker,
                "worker_exchange.native_output": native,
                "worker_exchange.world_restore": restoration}

    def test_success_seals_after_restoration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_id = "testing__C153046__NRS-484B-307-8c__motor_vehicle_driver__stopped_leftmost_clear"
            (root / "config.json").write_text(json.dumps({"selected_case_id": case_id,
                "case": {"case_id": case_id}}))
            events = []
            with patch.dict(sys.modules, self._modules(events)), \
                 patch("native_capture.capture", side_effect=lambda *args: (
                     events.append("capture"), {"trace": {"samples": 600}})[1]), \
                 patch("saved_measurement.finalize_attempt", side_effect=lambda *args: (
                     events.append("analysis"), {"case_id": case_id,
                                                 "measurement": {"site_packet_sha256": "abc"}})[1]):
                result = capture_original(root, "127.0.0.1", 2000, root / "site.json")
            self.assertEqual(events, ["settings", "capture", "restore", "analysis", "seal"])
            self.assertEqual(result["seal"], "worker-sealed-capture")
            self.assertEqual(json.loads((root / "acquisition-provenance.json").read_text())["provenance_kind"],
                             "native")

    def test_capture_failure_retains_status_and_restores(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_id = "testing__C153046__NRS-484B-307-8c__motor_vehicle_driver__stopped_leftmost_clear"
            (root / "config.json").write_text(json.dumps({"selected_case_id": case_id,
                "case": {"case_id": case_id}}))
            events = []
            def fail(*args):
                events.append("capture")
                raise ValueError("synthetic capture failure")
            with patch.dict(sys.modules, self._modules(events)), \
                 patch("native_capture.capture", side_effect=fail):
                with self.assertRaisesRegex(ValueError, "synthetic capture failure"):
                    capture_original(root, "127.0.0.1", 2000, root / "site.json")
            self.assertEqual(events, ["settings", "capture", "restore"])
            self.assertIn("capture: synthetic capture failure",
                          json.loads((root / "native-run-status.json").read_text())["errors"])


if __name__ == "__main__":
    unittest.main()
