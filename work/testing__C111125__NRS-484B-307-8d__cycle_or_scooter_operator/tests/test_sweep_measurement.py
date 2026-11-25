"""CPU probes of source-sealed realized judgment-sweep measurements."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sweep_measurement import ASSIGNMENT, main, measure


SCRATCH = Path(__file__).resolve().parents[3] / ".runtime-work" / "c111125-sweep-tests"


class SweepMeasurementTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case_id = ASSIGNMENT + "__detector_causality-0000"
        self.spec_id = ASSIGNMENT + "__detector_causality"
        self.proposal = {"sweeps_expanded": True,
                         "cases": [{"case_id": self.case_id, "target_type": "judgment_sweep",
                                    "sweep_id": self.spec_id, "sweep_spec_version": "frozen-v1",
                                    "sweep_point": {"detector_test_offset_m": 0.5}}],
                         "sweep_specs": [{"sweep_id": self.spec_id, "status": "complete",
                                          "spec_version": "frozen-v1", "selection_order": [self.case_id],
                                          "numeric_control_binding": {"original_readback_field": "detector_offset_m"},
                                          "axes": [{"variable": "detector_test_offset_m",
                                                    "observable": "observed_detector_offset", "unit": "m",
                                                    "measurement": {"original_readback_field": "detector_offset_m",
                                                                    "statistic": "mean"}}]}]}
        self.rows = [{"frame": index, "timestamp_s": index / 20,
                      "ego_station_m": 0.0 if index < 500 else 10.0,
                      "ego_speed_mps": 1.0 if index < 100 or index >= 500 else 0.0,
                      "detector_offset_m": 0.75 if index >= 100 else 99.0}
                     for index in range(900)]
        native = self._write("native.json", {"frames": self.rows})
        geometry = self._write("geometry.json", {"stop_boundary_station_m": 1.0,
                                                  "entry_station_m": 9.0})
        packet = self._write("packet.json", {"native_trace_ref": native,
                                             "geometry_ref": geometry, "frames": self.rows})
        self._write("attempt.json", {"case_id": self.case_id, "diagnostic_fixture": False,
                                     "packet_ref": packet})

    def _write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, separators=(",", ":")) + "\n")
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_realized_readback_excludes_startup_and_preserves_no_verdict(self):
        result = measure(self.proposal, self.case_id, self.root)
        self.assertEqual(result["realized_observables"],
                         {"observed_detector_offset": {"value": 0.75, "unit": "m"}})
        self.assertEqual(result["window_frames"], [100, 500])
        self.assertIsNone(result["legal_verdict"])
        self.assertFalse(result["physical_acceptance"])

    def test_tampered_original_and_missing_readback_rejected(self):
        native = self.root / "native.json"
        native.write_text(native.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            measure(self.proposal, self.case_id, self.root)
        bad_rows = [{**row, "detector_offset_m": None} for row in self.rows]
        native_ref = self._write("native.json", {"frames": bad_rows})
        packet = self._write("packet.json", {"native_trace_ref": native_ref,
                                             "geometry_ref": json.loads((self.root / "packet.json").read_text())["geometry_ref"],
                                             "frames": bad_rows})
        self._write("attempt.json", {"case_id": self.case_id, "diagnostic_fixture": False,
                                     "packet_ref": packet})
        with self.assertRaisesRegex(ValueError, "numeric sweep readback missing"):
            measure(self.proposal, self.case_id, self.root)

    def test_broken_original_clock_rejected(self):
        bad_rows = list(self.rows)
        bad_rows[130] = {**bad_rows[130], "timestamp_s": 7.0}
        native_ref = self._write("native.json", {"frames": bad_rows})
        packet = self._write("packet.json", {"native_trace_ref": native_ref,
                                             "geometry_ref": json.loads((self.root / "packet.json").read_text())["geometry_ref"],
                                             "frames": bad_rows})
        self._write("attempt.json", {"case_id": self.case_id, "diagnostic_fixture": False,
                                     "packet_ref": packet})
        with self.assertRaisesRegex(ValueError, "time sequence broken"):
            measure(self.proposal, self.case_id, self.root)

    def test_cli_writes_separate_reproducible_receipt(self):
        proposal_path = self.root / "proposal.json"
        proposal_path.write_text(json.dumps(self.proposal) + "\n")
        separate = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(separate.cleanup)
        output = Path(separate.name) / "measurement.json"
        argv = ["sweep_measurement.py", "--proposal", str(proposal_path),
                "--case", self.case_id, "--attempt", str(self.root),
                "--output", str(output)]
        with patch("sys.argv", argv):
            main()
        self.assertEqual(json.loads(output.read_text())["raw_sample_count"], 401)
        with patch("sys.argv", argv):
            with self.assertRaisesRegex(ValueError, "retain previous"):
                main()


if __name__ == "__main__":
    unittest.main()
