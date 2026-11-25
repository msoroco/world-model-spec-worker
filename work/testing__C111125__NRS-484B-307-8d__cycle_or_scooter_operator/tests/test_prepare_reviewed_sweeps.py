"""Diagnostic schema probes for reviewed-source sweep expansion."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from prepare_reviewed_sweeps import digest, prepare


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(__file__).resolve().parents[3] / ".runtime-work" / "c111125-sweep-tests"


class ReviewedSweepPreparationTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.authority = Path(self.temp.name)
        source = ROOT / "diagnostics" / "two_cycles_failed_detection"
        shutil.copytree(source / "source", self.authority / "source")
        site = json.loads((source / "native-site.json").read_text())
        site["reviewed_original_site"] = True
        self.site_path = self.authority / "site.json"
        self.site_path.write_text(json.dumps(site) + "\n")
        control = {"supported_numeric_controls": ["detector_test_offset_m", "directed_gap_s"]}
        self.control_path = self.authority / "control.json"
        self.control_path.write_text(json.dumps(control) + "\n")
        self.ranges_path = self.authority / "ranges.json"
        self.ranges_path.write_text(json.dumps({
            "reviewed_original_ranges": True, "site_sha256": digest(self.site_path),
            "control_ref": self.ref(self.control_path),
            "evidence_refs": [self.ref(self.authority / "source" / "map.json")],
            "sweeps": {
                "detector_causality": self.axis("detector_test_offset_m", "detector occupancy", "source/detector.json"),
                "directed_yield": self.axis("directed_gap_s", "directed participant gap", "source/map.json")
            }}) + "\n")

    def ref(self, path):
        return {"path": str(path.relative_to(self.authority)), "sha256": digest(path)}

    def axis(self, variable, observable, evidence):
        return {"variable": variable, "kind": "controller", "observable": observable,
                "unit": "m" if variable.endswith("_m") else "s",
                "min": 0.0, "max": 1.0, "spacing": 0.5,
                "measurement": {"method": "original Native readback", "time_window": "entry window", "statistic": "min"},
                "range_rationale": "diagnostic schema fixture only", "spacing_rationale": "diagnostic schema fixture only",
                "feasibility_evidence": "diagnostic schema fixture only",
                "feasibility_source_ref": self.ref(self.authority / evidence), "landmarks": []}

    def expand(self):
        return prepare(ROOT / "proposals" / "cases.json", self.authority,
                       self.ref(self.site_path), self.ref(self.ranges_path))

    def test_reviewed_shaped_packet_expands_two_sweeps_without_labels(self):
        proposal = self.expand()
        self.assertTrue(proposal["sweeps_expanded"])
        self.assertEqual([s["planned_case_count"] for s in proposal["sweep_specs"]], [3, 3])
        generated = [c for c in proposal["cases"] if c.get("sweep_id") in
                     {s["sweep_id"] for s in proposal["sweep_specs"]}]
        self.assertEqual(len(generated), 6)
        self.assertTrue(all("legal_verdict" not in c for c in generated))

    def test_missing_and_stale_original_source_rejected(self):
        (self.authority / "source" / "detector.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing source file"):
            self.expand()
        shutil.copy2(ROOT / "diagnostics" / "two_cycles_failed_detection" / "source" / "detector.json",
                     self.authority / "source" / "detector.json")
        (self.authority / "source" / "detector.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            self.expand()

    def test_stale_range_packet_and_unsupported_control_rejected(self):
        stale = self.ref(self.ranges_path)
        self.ranges_path.write_text(self.ranges_path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "reviewed sweep source stale"):
            prepare(ROOT / "proposals" / "cases.json", self.authority, self.ref(self.site_path), stale)
        ranges = json.loads(self.ranges_path.read_text())
        ranges["sweeps"]["directed_yield"]["variable"] = "unsupported_control"
        self.ranges_path.write_text(json.dumps(ranges) + "\n")
        with self.assertRaisesRegex(ValueError, "lacks sourced numeric adapter control"):
            self.expand()

    def test_diagnostic_site_rejected(self):
        site = json.loads(self.site_path.read_text())
        site["diagnostic_fixture"] = True
        self.site_path.write_text(json.dumps(site) + "\n")
        with self.assertRaisesRegex(ValueError, "reviewed original site authority missing"):
            self.expand()


if __name__ == "__main__":
    unittest.main()
