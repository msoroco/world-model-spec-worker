"""CPU positive/negative checks for fixed Native conditions and measured beam changes."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from comparison_audit import audit
from test_analysis import TEMP_ROOT, fixture

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
HIGH = next(x for x in PLAN["cases"] if x["case_id"].endswith("__oncoming_499_high"))
LOW = next(x for x in PLAN["cases"] if x["case_id"].endswith("__oncoming_499_low"))


def _change_case(root, case, *, bits):
    config_path = root / "config.json"
    config = json.loads(config_path.read_text())
    config["selected_case_id"] = case["case_id"]
    config["case_plan"] = case
    config_path.write_text(json.dumps(config) + "\n")
    site_path = root / "site-packet.json"
    site = json.loads(site_path.read_text())
    site["case_id"] = case["case_id"]
    site["requested_beam"] = case["requested_beam"]
    site_path.write_text(json.dumps(site) + "\n")
    state_path = root / "actor-state.jsonl"
    rows = [json.loads(x) for x in state_path.read_text().splitlines()]
    for row in rows:
        row["actors"]["ego"]["lamp_state_bits"] = bits
        row["actors"]["ego"]["lamp_command_bits"] = bits
    state_path.write_text("".join(json.dumps(x) + "\n" for x in rows))
    receipt_path = root / "native-source-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["case_id"] = case["case_id"]
    for name in ("site-packet.json", "actor-state.jsonl"):
        receipt["source_hashes"][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt) + "\n")


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="comparison-", dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.high = self.base / "high"
        self.low = self.base / "low"
        self.high.mkdir()
        self.low.mkdir()
        fixture(self.high)
        fixture(self.low)
        _change_case(self.high, HIGH, bits=8)

    def test_measured_beam_readback_difference(self):
        value = audit(self.high, self.low, "near_oncoming_glare",
                      diagnostic=True, expected_frames=9)
        self.assertTrue(value["fixed_source_conditions_verified"])
        self.assertEqual(value["observed_difference"]["first_unique_bits"], [8])
        self.assertEqual(value["observed_difference"]["second_unique_bits"], [4])

    def test_fixed_camera_change_rejected(self):
        path = self.low / "config.json"
        config = json.loads(path.read_text())
        config["camera_dimensions"] = {"approach": [16, 12]}
        path.write_text(json.dumps(config) + "\n")
        with self.assertRaisesRegex(ValueError, "fixed capture"):
            audit(self.high, self.low, "near_oncoming_glare",
                  diagnostic=True, expected_frames=9)

    def test_no_observed_beam_difference_rejected(self):
        _change_case(self.high, HIGH, bits=4)
        with self.assertRaisesRegex(ValueError, "did not change"):
            audit(self.high, self.low, "near_oncoming_glare",
                  diagnostic=True, expected_frames=9)


if __name__ == "__main__":
    unittest.main()
