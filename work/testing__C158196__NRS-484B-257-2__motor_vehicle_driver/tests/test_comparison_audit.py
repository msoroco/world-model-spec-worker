import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit
from test_saved_finalizer import saved_fixture


def prepare(root, suffix, state, controls):
    saved_fixture(root)
    config = json.loads((root / "config.json").read_text())
    config["selected_case_id"] = (
        "testing__C158196__NRS-484B-257-2__motor_vehicle_driver__" + suffix)
    config["motion"]["signal_state"] = state
    (root / "config.json").write_text(json.dumps(config) + "\n")
    inventory = json.loads((root / "entrance_inventory.json").read_text())
    inventory["entrances"][0]["device"] = "yield"
    (root / "entrance_inventory.json").write_text(json.dumps(inventory) + "\n")
    rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
    for row in rows:
        row["signal_state"] = state
        row["signal_controls_ego"] = controls
    (root / "crossing_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))


class ComparisonAuditTests(unittest.TestCase):
    def test_active_vs_off_and_changed_fixed_camera(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "first", Path(tmp) / "second"
            first.mkdir(); second.mkdir()
            prepare(first, "active_signal_controls", "Green", True)
            prepare(second, "signal_off_signed_duty", "Off", False)
            report = audit("active_vs_off_signal_exception", first, second)
            self.assertTrue(report["deliberate_difference_observed"])
            self.assertFalse(report["physical_acceptance_claimed"])
            config = json.loads((second / "config.json").read_text())
            config["cameras"][0]["width"] += 1
            (second / "config.json").write_text(json.dumps(config) + "\n")
            with self.assertRaisesRegex(ValueError, "Fixed comparison condition changed: cameras"):
                audit("active_vs_off_signal_exception", first, second)


if __name__ == "__main__":
    unittest.main()
