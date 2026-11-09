import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

root = Path.cwd()
native = root / "work" / "training__C111603__NRS-484B-307-9a__motor_vehicle_driver" / "native"
sys.path.insert(0, str(native))
from build import check
from saved import fixture, process
from prove_original_processing import prove

class ArrowRequest(unittest.TestCase):
    def setUp(self):
        self.bundle = native / "drafts" / "witness_2" / "fallback3"

    def test_exact_request(self):
        result = check(self.bundle)
        self.assertEqual(result["frames"], 480)
        self.assertFalse(result["delivery_ready"])

    def test_synthetic_saved_join(self):
        saved = process(self.bundle, fixture(self.bundle))
        self.assertEqual(saved["joined_video_frames"], 480)
        self.assertFalse(saved["original_native_observed"])
        self.assertIsNone(saved["legal_verdict"])

    def test_capture_entrypoint_preflight(self):
        completed = subprocess.run([sys.executable, str(native / "capture.py"),
            "--check", "--bundle", str(self.bundle)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["frames"], 480)
        self.assertFalse(result["original_native_observed"])

    def test_original_processor_source_shape(self):
        result = prove(self.bundle)
        self.assertEqual(result["positive_count"], 1)
        self.assertEqual(result["negative_count"], 9)
        self.assertFalse(result["original_native_observed"])
        self.assertFalse(result["delivery_ready"])

    def test_rehashed_signal_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            changed = Path(name)
            for file in self.bundle.iterdir():
                (changed / file.name).write_bytes(file.read_bytes())
            road = changed / "arrow-intersection.xodr"
            road.write_text(road.read_text().replace("green-right-arrow", "green-left-arrow"))
            config = changed / "config.json"
            value = json.loads(config.read_text())
            value["road_sha256"] = hashlib.sha256(road.read_bytes()).hexdigest()
            config.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                check(changed)
