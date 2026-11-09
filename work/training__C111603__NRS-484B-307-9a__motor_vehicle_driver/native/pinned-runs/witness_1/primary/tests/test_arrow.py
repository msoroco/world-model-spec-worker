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
from prove_original_processing import prove, fixture as original_fixture
from fallback_quality import request_measurements, decide, from_capture

class ArrowRequest(unittest.TestCase):
    def setUp(self):
        self.bundle = native / "drafts" / "witness_1" / "primary"

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

    def test_fallback_quality_preflight(self):
        measured = request_measurements(self.bundle)
        decision = decide(measured, allow_synthetic=True) if measured["camera_policy"] == "standard" else None
        if decision is not None:
            self.assertIsNone(decision["selected_candidate"])
            self.assertFalse(decision["original_native_observed"])
        with self.assertRaises(ValueError):
            decide(measured)

    def test_capture_bound_quality_shape(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            review = original_fixture(self.bundle, directory)
            value = json.loads(review.read_text())
            value["quality_signal_other_visible_frames"] = list(range(480))
            review.write_text(json.dumps(value))
            if "primary" == "primary":
                result = from_capture(self.bundle, directory, review, synthetic_fixture=True)
                self.assertTrue(result["triggers"]["fallback1"])
                self.assertFalse(result["original_native_observed"])
            else:
                with self.assertRaises(ValueError):
                    from_capture(self.bundle, directory, review, synthetic_fixture=True)

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
