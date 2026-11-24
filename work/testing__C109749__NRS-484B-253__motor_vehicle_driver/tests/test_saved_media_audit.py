import hashlib
import json
import pathlib
import subprocess
import sys
import unittest

import test_native_acquisition as acquisition_test

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_media_audit import audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SavedMediaAudit(unittest.TestCase):
    setUp = acquisition_test.NativeAcquisition.setUp
    tearDown = acquisition_test.NativeAcquisition.tearDown
    write_map = acquisition_test.NativeAcquisition.write_map
    run_capture = acquisition_test.NativeAcquisition.run_capture

    def make_attempt(self):
        self.adapter.native_origin = True
        self.packet["reviewed_original_map"] = True
        self.write_map()
        self.run_capture()
        return self.root / "attempt"

    def test_full_decode_and_cli_replay(self):
        attempt = self.make_attempt()
        result = audit(attempt, case_id=self.case)
        self.assertEqual((result["frame_count"], result["decoded_images"]), (2, 8))
        self.assertEqual(result["camera_dimensions"]["overview"], [4, 4])
        output = self.root / "audit.json"
        completed = subprocess.run([sys.executable, str(ROOT / "saved_media_audit.py"),
                                    "--attempt", str(attempt), "--case", self.case,
                                    "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(output.read_text()), result)

    def test_full_900_tick_four_camera_decode(self):
        self.adapter.native_origin = True
        self.packet["reviewed_original_map"] = True
        self.write_map()
        attempt = self.root / "long-attempt"
        from native_acquisition import capture
        capture(adapter=self.adapter, case_id=self.case, map_path=self.map_path,
                output=attempt, frame_count=900)
        result = audit(attempt, case_id=self.case)
        self.assertEqual((result["frame_count"], result["decoded_images"]), (900, 3600))

    def test_default_rejects_diagnostic_without_output(self):
        self.run_capture()
        output = self.root / "audit.json"
        completed = subprocess.run([sys.executable, str(ROOT / "saved_media_audit.py"),
                                    "--attempt", str(self.root / "attempt"), "--case", self.case,
                                    "--output", str(output)], capture_output=True, text=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("diagnostic fixture", completed.stderr)
        self.assertFalse(output.exists())

    def test_rejects_truncated_png_after_resealing_hashes(self):
        attempt = self.make_attempt()
        image = attempt / "original-frames" / "000000100-overview.png"
        image.write_bytes(image.read_bytes()[:30])
        frame_map_path = attempt / "original-frame-map.json"
        frame_map = json.loads(frame_map_path.read_text())
        frame_map["frames"][0]["cameras"]["overview"]["sha256"] = sha(image)
        frame_map_path.write_text(json.dumps(frame_map) + "\n")
        receipt_path = attempt / "acquisition-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["frame_map_sha256"] = sha(frame_map_path)
        receipt_path.write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "fully decode"):
            audit(attempt, case_id=self.case)

    def test_rejects_duplicate_source_path(self):
        attempt = self.make_attempt()
        frame_map_path = attempt / "original-frame-map.json"
        frame_map = json.loads(frame_map_path.read_text())
        frame_map["frames"][1]["cameras"]["overview"] = frame_map["frames"][0]["cameras"]["overview"]
        frame_map_path.write_text(json.dumps(frame_map) + "\n")
        receipt_path = attempt / "acquisition-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["frame_map_sha256"] = sha(frame_map_path)
        receipt_path.write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "reused"):
            audit(attempt, case_id=self.case)


if __name__ == "__main__":
    unittest.main()
