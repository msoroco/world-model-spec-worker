import sys
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from comparison_audit import FIXED, audit
from delivery_audit import video_decode
from analysis import audit_camera_sources
from native_construction import ASSIGNMENT


def report(variant, *, signal, check):
    context = {key: "source-" + key for key in FIXED}
    return {"format": "c144550-saved-lane-change-report-v1",
            "case_id": ASSIGNMENT + "__" + variant,
            "original_source_hashes": {"frame_map.json": "a" * 64},
            "legal_verdict_claimed": False, "fixed_context": context,
            "measurements": {"signal_precedes_center_departure": signal,
                             "driver_check_observed_before_departure": check}}


class SavedAuditsTests(unittest.TestCase):
    def test_accepted_source_pairs_require_original_measured_difference(self):
        pairs = (("accepted-source-1-signal-control", "accepted_source_1",
                  "signal_missing", False, True),
                 ("accepted-source-2-check-control", "accepted_source_2",
                  "check_missing", True, False),
                 ("accepted-source-3-signal-control", "accepted_source_3",
                  "signal_missing", False, True))
        for comparison, accepted, contrast, contrast_signal, contrast_check in pairs:
            with self.subTest(comparison=comparison):
                first = report(accepted, signal=True, check=True)
                second = report(contrast, signal=contrast_signal,
                                check=contrast_check)
                self.assertTrue(audit(comparison, {accepted: first,
                                                   contrast: second})["passed"])
                second["measurements"] = dict(first["measurements"])
                with self.assertRaisesRegex(ValueError, "difference"):
                    audit(comparison, {accepted: first, contrast: second})
                second["measurements"] = {
                    "signal_precedes_center_departure": contrast_signal,
                    "driver_check_observed_before_departure": contrast_check}
                second["fixed_context"]["target_traffic_plan_sha256"] = "changed"
                with self.assertRaisesRegex(ValueError, "fixed"):
                    audit(comparison, {accepted: first, contrast: second})

    def test_signal_pair_holds_check_and_changes_signal(self):
        result = audit("signal-prerequisite-control", {
            "both_observed": report("both_observed", signal=True, check=True),
            "signal_missing": report("signal_missing", signal=False, check=True)})
        self.assertTrue(result["passed"])
        self.assertFalse(result["physical_safety_or_legal_judgment_claimed"])

    def test_check_pair_holds_signal_and_changes_check(self):
        result = audit("check-prerequisite-control", {
            "both_observed": report("both_observed", signal=True, check=True),
            "check_missing": report("check_missing", signal=True, check=False)})
        self.assertTrue(result["passed"])

    def test_fixed_context_or_held_conjunct_change_rejected(self):
        first = report("both_observed", signal=True, check=True)
        second = report("signal_missing", signal=False, check=True)
        second["fixed_context"]["target_traffic_plan_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "fixed"):
            audit("signal-prerequisite-control", {"both_observed": first,
                                                  "signal_missing": second})
        second = report("signal_missing", signal=False, check=False)
        with self.assertRaisesRegex(ValueError, "held"):
            audit("signal-prerequisite-control", {"both_observed": first,
                                                  "signal_missing": second})

    def test_conjunct_cannot_be_inferred_from_label(self):
        first = report("both_observed", signal=False, check=True)
        second = report("signal_missing", signal=False, check=True)
        with self.assertRaisesRegex(ValueError, "difference"):
            audit("signal-prerequisite-control", {"both_observed": first,
                                                  "signal_missing": second})

    def test_camera_join_rejects_changed_native_time_before_pixels(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as temp:
            root = Path(temp)
            (root / "original-camera-frames").mkdir()
            manifest = [{"frame": i, "native_frame": i + 10,
                         "native_elapsed_s": i * .05,
                         "views": {name: {} for name in
                             ("overview", "approach", "reference_corner", "driver_reference")}}
                        for i in range(900)]
            manifest[0]["native_elapsed_s"] = .1
            path = root / "original-camera-frames/camera-manifest.json"
            path.write_text(json.dumps(manifest) + "\n")
            (root / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "native", "diagnostic_fixture": False}) + "\n")
            from hashlib import sha256
            with self.assertRaisesRegex(ValueError, "frame/time join"):
                audit_camera_sources(root, {"camera_manifest": {
                    "sha256": sha256(path.read_bytes()).hexdigest()}},
                    [{"frame": i + 10, "t_s": i * .05} for i in range(900)])

    def test_full_video_decode_failure_is_rejected_after_probe(self):
        from types import SimpleNamespace
        probe = SimpleNamespace(returncode=0, stdout=json.dumps({"streams": [
            {"nb_read_frames": "900", "width": 1280, "height": 720}]}))
        decode = SimpleNamespace(returncode=1)
        with patch("delivery_audit.subprocess.run", side_effect=[probe, decode]) as called:
            with self.assertRaisesRegex(ValueError, "full video pixel decode"):
                video_decode(Path("dummy.mkv"), 900, (1280, 720))
        self.assertEqual(called.call_count, 2)


if __name__ == "__main__":
    unittest.main()
