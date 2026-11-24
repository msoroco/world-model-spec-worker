import hashlib
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from original_adapters import OriginalInstrumentLog, capture_with_original_adapters
import test_native_capture
from camera_recorder import CAMERAS
from saved_finalizer import finalize

CASE = test_native_capture.CASE


class OriginalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_capture.CaptureTests(
            methodName="test_full_source_seal_and_distinct_command_readback")
        self.fixture.setUp()
        self.log = self.fixture.folder / "instrument.jsonl"
        self.rows = [dict(case_id=CASE, native_frame=frame,
                          sample_id=f"original-{frame}",
                          siren_active=161 <= frame <= 441,
                          warning_lamp_active=False,
                          source_type="instrument_telemetry",
                          source_citation="fixture original instrument")
                     for frame in range(1, 901)]
        self.write_log()

    def tearDown(self):
        self.fixture.tearDown()

    def write_log(self):
        raw = b"".join(json.dumps(row, sort_keys=True).encode() + b"\n" for row in self.rows)
        self.log.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def reader(self, **changes):
        opts = dict(case_id=CASE, expected_sha256=self.write_log(),
                    source_type="instrument_telemetry",
                    source_citation="fixture original instrument")
        opts.update(changes)
        return OriginalInstrumentLog(self.log, **opts)

    def test_original_log_case_frame_and_hash_are_bound(self):
        adapter = self.reader()
        self.assertEqual(json.loads(adapter.sample(None, 161))["sample_id"], "original-161")
        with self.assertRaisesRegex(ValueError, "sample missing"):
            adapter.sample(None, 901)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.reader(expected_sha256="0" * 64)
        self.rows[2]["case_id"] = CASE + "-other"
        with self.assertRaisesRegex(ValueError, "case mismatch"):
            self.reader()
        self.rows[2]["case_id"] = CASE
        self.rows[2]["native_frame"] = 100
        with self.assertRaisesRegex(ValueError, "frame sequence"):
            self.reader()

    def test_capture_consumes_original_log_and_camera_pixels(self):
        image = types.SimpleNamespace(width=2, height=2,
                                      raw_data=bytes([3, 2, 1, 255] * 4))
        def camera_read(frame):
            image.frame = frame
            return {key: image for key in CAMERAS}
        commands = []
        receipt = capture_with_original_adapters(
            self.fixture.world, self.fixture.api, case_id=CASE,
            site_packet=self.fixture.site, dispatch_document=self.fixture.dispatch,
            equipment_document=self.fixture.equipment, instrument_log=self.log,
            instrument_sha256=self.write_log(),
            instrument_source_type="instrument_telemetry",
            instrument_source_citation="fixture original instrument",
            output=self.fixture.folder / "out",
            device_command=lambda ego, *, siren, lamps: commands.append((siren, lamps)),
            drive_step=lambda ego, pedestrian, tick: None,
            camera_frame_reader=camera_read,
            camera_source_ids={key: "fixture-" + key for key in CAMERAS},
            camera_sizes={key: (2, 2) for key in CAMERAS}, diagnostic=True)
        self.assertEqual(receipt["native_last_frame"], 900)
        self.assertIn("device_samples", receipt["sources"])
        self.assertTrue((self.fixture.folder / "out" / "camera_media.json").exists())
        self.assertEqual(finalize(self.fixture.folder / "out", case_id=CASE)["native_frame_count"], 900)
        self.assertEqual(commands[-1], (False, False))

    def test_production_rejects_diagnostic_camera_dimensions_before_spawn(self):
        with self.assertRaisesRegex(ValueError, "pinned profile"):
            capture_with_original_adapters(
                self.fixture.world, self.fixture.api, case_id=CASE,
                site_packet=self.fixture.site, dispatch_document=self.fixture.dispatch,
                equipment_document=self.fixture.equipment, instrument_log=self.log,
                instrument_sha256=self.write_log(),
                instrument_source_type="instrument_telemetry",
                instrument_source_citation="fixture original instrument",
                output=self.fixture.folder / "out",
                device_command=lambda ego, *, siren, lamps: None,
                drive_step=lambda ego, pedestrian, tick: None,
                camera_frame_reader=lambda frame: {},
                camera_source_ids={key: "fixture-" + key for key in CAMERAS},
                camera_sizes={key: (2, 2) for key in CAMERAS})
        self.assertFalse(self.fixture.world.actors)


if __name__ == "__main__":
    unittest.main()
