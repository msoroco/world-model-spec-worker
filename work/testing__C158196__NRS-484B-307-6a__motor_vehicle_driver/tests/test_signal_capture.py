"""CPU protocol checks for 900 joined Native-shaped signal frames."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from signal_capture import capture
from signal_capture_audit import audit
from test_signal_measurement import FakeAdapter, SOURCE, scene


class CaptureAdapter(FakeAdapter):
    native_attested = True

    def __init__(self):
        super().__init__()
        self.index = -1
        self.destroyed = False
        self.restored = False

    def tick(self, built):
        self.index += 1
        return {"frame": 1000 + self.index, "time_s": 50 + self.index / 20}

    def read_signal_row(self, frame, built, scene_data):
        i = self.index
        color = "green" if i < 100 else "yellow" if i < 500 else "red"
        return {"origin": "native_world_snapshot", "native_frame": frame,
                "native_time_s": 50 + i / 20,
                "heading_deg": 0.0, "speed_mps": 5.0,
                "ego_front_signed_distance_m": i - 200 + .25,
                "ego_vertices": [[float(i), float(j), 0.0] for j in range(8)],
                "ego_geometry_source": SOURCE,
                "signals": [{"signal_id": "head1", "route_id": "ego_route",
                             "kind": "vehicular", "official": True,
                             "facing_ego": True, "state": color,
                             "flashing": False, "companion_lamps_on": [],
                             "source": SOURCE}]}

    def read_cameras(self, frame, built):
        return {name: {"frame": frame, "png": b"\x89PNG\r\n\x1a\nfixture"}
                for name in ("overview", "approach", "reference_corner", "driver_reference")}

    def source_bindings(self, scene_data):
        return {"intersection_polygon": SOURCE, "route_connectivity": SOURCE,
                "device_route_binding": SOURCE, "native_result": SOURCE}

    def brake(self):
        pass

    def destroy(self, actor):
        self.destroyed = True

    def restore(self):
        self.restored = True


class CaptureTest(unittest.TestCase):
    def test_original_frame_join_and_cleanup(self):
        root = BASE.parents[1] / ".runtime-work" / "c158196-capture-fixture"
        root.mkdir(parents=True, exist_ok=True)
        destination = root / "original"
        if destination.exists():
            import shutil
            shutil.rmtree(destination)
        adapter = CaptureAdapter()

        def encode(command, **kwargs):
            Path(command[-1]).write_bytes(b"fixture diagnostic mkv")

        with patch("signal_capture.subprocess.run", side_effect=encode):
            observed = capture(adapter, scene(), "enters_yellow", destination)
        self.assertEqual(observed["entry_observation"], "yellow_both_samples")
        self.assertEqual(observed["frame_count"], 900)
        self.assertEqual(len((destination / "trace.jsonl").read_text().splitlines()), 900)
        self.assertEqual(len((destination / "video_frames.jsonl").read_text().splitlines()), 900)
        self.assertFalse(json.loads((destination / "original-source-receipt.json").read_text())
                         ["physical_acceptance"])
        self.assertTrue(adapter.destroyed and adapter.restored)

    def test_source_audit_rejects_changed_trace(self):
        root = BASE.parents[1] / ".runtime-work" / "c158196-audit-fixture"
        root.mkdir(parents=True, exist_ok=True)
        destination = root / "original"
        if destination.exists():
            import shutil
            shutil.rmtree(destination)

        def encode(command, **kwargs):
            Path(command[-1]).write_bytes(b"fixture diagnostic mkv")

        with patch("signal_capture.subprocess.run", side_effect=encode):
            capture(CaptureAdapter(), scene(), "enters_yellow", destination)
        class Probe:
            stdout = json.dumps({"streams": [{"r_frame_rate": "20/1",
                                               "nb_read_frames": "900"}]})
        decoded = []
        result = audit(destination, "enters_yellow", probe=lambda cmd: Probe(),
                       decoder=lambda cmd: decoded.append(cmd))
        self.assertEqual(result["frame_count"], 900)
        self.assertFalse(result["actual_pixels_reviewed"])
        self.assertEqual(len(decoded), 4)
        trace = destination / "trace.jsonl"
        trace.write_text(trace.read_text() + "{}\n")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            audit(destination, "enters_yellow", probe=lambda cmd: Probe(),
                  decoder=lambda cmd: decoded.append(cmd))


if __name__ == "__main__":
    unittest.main()
