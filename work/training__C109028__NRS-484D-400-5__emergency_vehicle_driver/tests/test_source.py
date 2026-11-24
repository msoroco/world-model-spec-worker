import json
from pathlib import Path
import tempfile
import unittest
from runner import check
from prove import make_source
from measure import measure
from audit import audit
from prove import BRANCHES
from source_acquisition import validate_audio, validate_dispatch
from audit_original import PAIRS
from geometry import check as check_geometry
from motion import check as check_motion
from finalize import siren_source_measurement

class SourceContract(unittest.TestCase):
    def test_exact_plan(self):
        row = check()
        self.assertEqual(row["frames"], 600)
        self.assertFalse(row["siren_output_observed"])

    def test_source_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            files = make_source(Path(temp), "probe_a")
            result = measure(*files)
            self.assertEqual(result["siren_observed_frames"], 200)
            self.assertEqual(result["siren_outside_documented_response_frames"], 0)
            self.assertIsNone(result["physical_legal_verdict"])

    def test_source_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            a, b = base / "probe_a", base / "probe_b"
            a.mkdir()
            b.mkdir()
            result = audit(make_source(a, "probe_a"), make_source(b, "probe_b"))
            self.assertTrue(result["passed"])
            self.assertEqual(result["outside_documented_response_frames"], [0, 200])

    def test_every_statutory_branch(self):
        with tempfile.TemporaryDirectory() as temp:
            for branch, policy in BRANCHES.items():
                base = Path(temp) / branch
                base.mkdir()
                result = measure(*make_source(base, branch))
                self.assertEqual(result["siren_observed_frames"], 200 if policy["siren"] else 0)
                self.assertEqual(result["warning_lamp_observed_frames"], 250 if policy["lamp"] else 0)
                self.assertEqual(result["siren_outside_documented_response_frames"],
                                 200 if branch == "probe_b" else 0)
                self.assertIsNone(result["physical_legal_verdict"])

    def test_source_acquisition_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            files = make_source(base, "probe_a")
            with self.assertRaisesRegex(ValueError, "Missing original microphone"):
                validate_audio(base / "missing.wav", base / "audio.jsonl", files[2])
            with self.assertRaisesRegex(ValueError, "Missing original dispatch"):
                validate_dispatch(files[3], files[2], base / "missing-dispatch.json")

    def test_saved_source_requires_original_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            make_source(base, "probe_a")
            with self.assertRaisesRegex(ValueError, "Missing required source: capture/manifest.json"):
                siren_source_measurement(base)

    def test_exact_source_comparison_inventory(self):
        self.assertEqual(set(PAIRS), {
            "call_vs_ordinary_siren", "call_vs_pursuit_siren",
            "call_siren_vs_lamps_only", "call_vs_ordinary_lamps_only"})

    def test_crossroads_and_shared_control(self):
        geometry = check_geometry()
        self.assertEqual(geometry["crossing_xy_m"], [50.0, 0])
        config = json.loads((Path("config.json")).read_text())
        motion = check_motion(config)
        self.assertTrue(motion["ego_crosses_authored_junction"])
        self.assertFalse(motion["physical_or_audio_success_claimed"])
