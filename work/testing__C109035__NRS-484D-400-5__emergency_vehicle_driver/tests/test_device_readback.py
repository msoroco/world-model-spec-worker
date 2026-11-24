import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from device_readback import DeviceReadback


class DeviceReadbackTests(unittest.TestCase):
    def sample(self, frame, **changes):
        obj = {"native_frame": frame, "sample_id": f"instrument-{frame}",
               "siren_active": frame == 2, "warning_lamp_active": True,
               "source_type": "instrument_telemetry", "source_citation": "fixture instrument"}
        obj.update(changes)
        return json.dumps(obj, sort_keys=True).encode()

    def reader(self, fn=None):
        return DeviceReadback(fn or (lambda ego, frame: self.sample(frame)),
                              source_type="instrument_telemetry",
                              source_citation="fixture instrument")

    def test_frame_join_and_original_sample_seal(self):
        reader = self.reader()
        self.assertFalse(reader.for_frame(object(), 1)["siren_active"])
        self.assertTrue(reader.for_frame(object(), 2)["siren_active"])
        with tempfile.TemporaryDirectory() as folder:
            source = reader.seal(Path(folder), 1, 2)
            data = (Path(folder) / source["path"]).read_bytes()
            self.assertEqual(source["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual([json.loads(row)["native_frame"] for row in data.splitlines()], [1, 2])
            with self.assertRaisesRegex(ValueError, "already exist"):
                reader.seal(Path(folder), 1, 2)

    def test_missing_stale_and_command_echo_sources_rejected(self):
        with self.assertRaisesRegex(ValueError, "instrument source type"):
            DeviceReadback(lambda ego, frame: b"{}", source_type="command_echo", source_citation="x")
        for changed, error in [({"native_frame": 99}, "frame mismatch"),
                               ({"sample_id": ""}, "identity"),
                               ({"siren_active": 1}, "state missing"),
                               ({"siren_commanded": True}, "Command fields"),
                               ({"source_citation": "other"}, "source mismatch")]:
            reader = self.reader(lambda ego, frame: self.sample(frame, **changed))
            with self.assertRaisesRegex(ValueError, error):
                reader.for_frame(object(), 1)
        reader = self.reader()
        reader.for_frame(object(), 1)
        with self.assertRaisesRegex(ValueError, "frame gap"):
            reader.for_frame(object(), 3)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "count incomplete"):
                reader.seal(Path(folder), 1, 2)

    def test_native_capture_retains_original_instrument_samples(self):
        from test_native_capture import CaptureTests
        fixture = CaptureTests(methodName="test_full_source_seal_and_distinct_command_readback")
        fixture.setUp()
        try:
            commands = []
            reader = self.reader(lambda ego, frame: self.sample(frame, siren_active=commands[-1][0],
                                                                  warning_lamp_active=commands[-1][1]))
            receipt = fixture.run_capture(
                device_command=lambda ego, *, siren, lamps: commands.append((siren, lamps)),
                device_readback=reader)
            source = receipt["sources"]["device_samples"]
            data = (fixture.folder / "out" / source["path"]).read_bytes()
            self.assertEqual(source["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(len(data.splitlines()), 900)
            self.assertEqual(json.loads(data.splitlines()[0])["native_frame"], 1)
            from saved_finalizer import finalize
            result = finalize(fixture.folder / "out", case_id=receipt["case_id"])
            self.assertEqual(result["native_frame_count"], 900)
            sample_rows = data.splitlines()
            altered = json.loads(sample_rows[0])
            altered["siren_active"] = not altered["siren_active"]
            sample_rows[0] = json.dumps(altered, sort_keys=True).encode()
            changed = b"\n".join(sample_rows) + b"\n"
            (fixture.folder / "out" / source["path"]).write_bytes(changed)
            receipt["sources"]["device_samples"]["sha256"] = hashlib.sha256(changed).hexdigest()
            (fixture.folder / "out" / "capture_receipt.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "sample and trace mismatch"):
                finalize(fixture.folder / "out", case_id=receipt["case_id"])
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
