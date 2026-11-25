"""Executable source binding for reviewed numeric Native controls."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from sweep_control import apply_sweep_control
from prepare_reviewed_sweeps import ASSIGNMENT


SCRATCH = Path(__file__).resolve().parents[3] / ".runtime-work" / "c111125-control-tests"


class Adapter:
    def __init__(self):
        self.calls = []

    def set_detector_offset(self, *, value, case_id, control_sha256):
        self.calls.append((value, case_id, control_sha256))
        return {"case_id": case_id, "control_sha256": control_sha256,
                "requested_setpoint": value,
                "original_readback_field": "detector_offset_m"}


class SweepControlTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + "__detector_causality-0000"
        self.site_sha = "1" * 64
        control = {"reviewed_original_controls": True, "site_sha256": self.site_sha,
                   "supported_numeric_controls": [{"name": "detector_test_offset_m",
                                                   "adapter_method": "set_detector_offset",
                                                   "original_readback_field": "detector_offset_m",
                                                   "unit": "m"}]}
        path = self.root / "controls.json"
        path.write_text(json.dumps(control) + "\n", encoding="utf-8")
        self.sha = hashlib.sha256(path.read_bytes()).hexdigest()
        self.ref = {"path": "controls.json", "sha256": self.sha}
        self.proposal = {"sweeps_expanded": True,
                         "reviewed_sweep_authority": {"control_sha256": self.sha,
                                                      "site_sha256": self.site_sha},
                         "cases": [{"case_id": self.case,
                                    "target_type": "judgment_sweep",
                                    "sweep_id": "detector_causality",
                                    "sweep_spec_version": "v1",
                                    "sweep_point": {"detector_test_offset_m": 0.5}}],
                         "sweep_specs": [{"sweep_id": "detector_causality",
                                          "status": "complete", "spec_version": "v1",
                                          "selection_order": [self.case],
                                          "numeric_control_binding": {
                                              "control_sha256": self.sha,
                                              "adapter_method": "set_detector_offset",
                                              "original_readback_field": "detector_offset_m"},
                                          "axes": [{"variable": "detector_test_offset_m",
                                                    "unit": "m", "min": 0.0, "max": 1.0}]}]}

    def test_applies_source_bound_request_without_acceptance_claim(self):
        adapter = Adapter()
        receipt = apply_sweep_control(self.proposal, self.case, self.root,
                                      self.ref, adapter)
        self.assertEqual(adapter.calls, [(0.5, self.case, self.sha)])
        self.assertFalse(receipt["physical_acceptance"])
        self.assertIsNone(receipt["legal_verdict"])

    def test_stale_source_and_unsupported_method_never_call_adapter(self):
        adapter = Adapter()
        (self.root / "controls.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source stale"):
            apply_sweep_control(self.proposal, self.case, self.root, self.ref, adapter)
        self.assertEqual(adapter.calls, [])
        control = {"reviewed_original_controls": True, "site_sha256": self.site_sha,
                   "supported_numeric_controls": [{"name": "detector_test_offset_m",
                                                   "adapter_method": "unknown_method",
                                                   "original_readback_field": "detector_offset_m",
                                                   "unit": "m"}]}
        path = self.root / "controls.json"
        path.write_text(json.dumps(control) + "\n", encoding="utf-8")
        new_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        self.ref["sha256"] = new_sha
        self.proposal["reviewed_sweep_authority"]["control_sha256"] = new_sha
        self.proposal["sweep_specs"][0]["numeric_control_binding"]["control_sha256"] = new_sha
        with self.assertRaisesRegex(ValueError, "numeric adapter and readback differ"):
            apply_sweep_control(self.proposal, self.case, self.root, self.ref, adapter)
        self.assertEqual(adapter.calls, [])

    def test_out_of_range_request_never_calls_adapter(self):
        adapter = Adapter()
        self.proposal["cases"][0]["sweep_point"]["detector_test_offset_m"] = 1.5
        with self.assertRaisesRegex(ValueError, "outside reviewed physical range"):
            apply_sweep_control(self.proposal, self.case, self.root, self.ref, adapter)
        self.assertEqual(adapter.calls, [])

    def test_control_from_another_reviewed_site_never_calls_adapter(self):
        adapter = Adapter()
        self.proposal["reviewed_sweep_authority"]["site_sha256"] = "2" * 64
        with self.assertRaisesRegex(ValueError, "reviewed original numeric control missing"):
            apply_sweep_control(self.proposal, self.case, self.root, self.ref, adapter)
        self.assertEqual(adapter.calls, [])


if __name__ == "__main__":
    unittest.main()
