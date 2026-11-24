import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import saved_finalizer

CASE = saved_finalizer.PREFIX + "response_siren_pedestrian"


class SavedFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.receipt = {
            "case_id": CASE, "source_kind": "original_capture",
            "site_packet_sha256": hashlib.sha256(b"reviewed-site-fixture").hexdigest(),
            "native_first_frame": 101, "native_last_frame": 1000,
            "physical_acceptance_claimed": False, "sources": {},
        }
        rows = []
        cameras = []
        for tick in range(900):
            on = 160 <= tick <= 440
            rows.append({"frame": tick, "native_frame": 101 + tick,
                         "elapsed_s": tick / 20, "siren_commanded": on,
                         "warning_lamp_commanded": False, "siren_active": on,
                         "warning_lamp_active": False,
                         "device_source_type": "instrument_fixture",
                         "device_source_citation": "synthetic CPU fixture"})
            cameras.append({"frame": tick, "native_frame": 101 + tick,
                            "sources": {key: f"fixture-{key}-{tick}" for key in
                                        ("overview", "approach", "reference_corner", "driver_reference")}})
        self.write_source("device_trace", rows, "jsonl")
        self.write_source("camera_trace", cameras, "jsonl")
        self.write_source("dispatch_context", {
            "case_id": CASE, "source_kind": "dispatch_context", "reviewer": "CPU fixture",
            "source_citation": "synthetic CPU fixture", "source_status": "documented",
            "event": "emergency_call", "event_interval_frames": [100, 500]}, "json")
        self.write_source("equipment_record", {
            "case_id": CASE, "source_kind": "equipment_record", "reviewer": "CPU fixture",
            "source_citation": "synthetic CPU fixture", "authorization_source": "fixture",
            "device_installation_source": "fixture", "audibility_500ft_status": "unknown"}, "json")
        self.save_receipt()

    def tearDown(self):
        self.temp.cleanup()

    def write_source(self, name, value, extension):
        data = ("".join(json.dumps(row) + "\n" for row in value) if extension == "jsonl"
                else json.dumps(value) + "\n").encode()
        path = name + "." + extension
        (self.folder / path).write_bytes(data)
        self.receipt["sources"][name] = {"path": path, "sha256": hashlib.sha256(data).hexdigest()}

    def save_receipt(self):
        (self.folder / "capture_receipt.json").write_text(json.dumps(self.receipt) + "\n")

    def test_positive_saved_measurement_stays_observational(self):
        result = saved_finalizer.finalize(self.folder, case_id=CASE)
        self.assertEqual(result["native_frame_count"], 900)
        self.assertEqual(result["commanded_siren_frames"], 281)
        self.assertEqual(result["observed"]["observed_siren_frames"], 281)
        self.assertEqual(result["physical_completion"], "unverified")
        self.assertIsNone(result["legal_conclusion"])

    def test_cross_case_document_rejected(self):
        value = json.loads((self.folder / "equipment_record.json").read_text())
        value["case_id"] = saved_finalizer.PREFIX + "unqualified_siren"
        self.write_source("equipment_record", value, "json")
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "source case identity"):
            saved_finalizer.finalize(self.folder, case_id=CASE)

    def test_event_mismatch_rejected(self):
        value = json.loads((self.folder / "dispatch_context.json").read_text())
        value["event"] = "none"
        self.write_source("dispatch_context", value, "json")
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "Documented event differs"):
            saved_finalizer.finalize(self.folder, case_id=CASE)

    def test_native_frame_gap_rejected_even_when_rehashed(self):
        rows = [json.loads(line) for line in (self.folder / "device_trace.jsonl").read_text().splitlines()]
        rows[400]["native_frame"] += 1
        self.write_source("device_trace", rows, "jsonl")
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "native device frame gap"):
            saved_finalizer.finalize(self.folder, case_id=CASE)

    def test_wrong_case_command_rejected(self):
        rows = [json.loads(line) for line in (self.folder / "device_trace.jsonl").read_text().splitlines()]
        for row in rows:
            row["siren_commanded"] = False
        self.write_source("device_trace", rows, "jsonl")
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "Recorded command differs"):
            saved_finalizer.finalize(self.folder, case_id=CASE)

    def test_tampered_source_rejected(self):
        with (self.folder / "device_trace.jsonl").open("ab") as handle:
            handle.write(b"tamper\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            saved_finalizer.finalize(self.folder, case_id=CASE)

    def test_source_through_symlinked_parent_rejected(self):
        (self.folder / "alias").symlink_to(self.folder, target_is_directory=True)
        self.receipt["sources"]["device_trace"]["path"] = "alias/device_trace.jsonl"
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "symlinked"):
            saved_finalizer.finalize(self.folder, case_id=CASE)

    def test_absolute_and_parent_traversal_rejected(self):
        for path in (str(self.folder / "device_trace.jsonl"),
                     "../device_trace.jsonl", "alias/../device_trace.jsonl"):
            self.receipt["sources"]["device_trace"]["path"] = path
            self.save_receipt()
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "path invalid"):
                saved_finalizer.finalize(self.folder, case_id=CASE)


if __name__ == "__main__":
    unittest.main()
