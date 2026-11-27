import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c393262_bus_duration", ROOT / "bus_duration.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DurationTest(unittest.TestCase):
    def test_all_six_exact_cases_and_source_gates(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        self.assertEqual(len(plan["cases"]), 6)
        for case in plan["cases"]:
            suffix = case["case_id"].split("__")[-1]
            refs = json.loads((ROOT / "cases" / suffix / "diagnostic-refs.json").read_text())
            report = module.measure(ROOT, refs, diagnostic=True)
            self.assertEqual(report["conduct"], case["conduct"])
            self.assertAlmostEqual(report["observed_duration_s"], case["diagnostic_duration_s"])
            self.assertIsNone(report["legal_verdict"])
            with self.assertRaisesRegex(ValueError, "synthetic diagnostic"):
                module.measure(ROOT, refs)
            changed = dict(refs)
            changed["activity"] = {"path": refs["activity"]["path"], "sha256": "0" * 64}
            with self.assertRaisesRegex(ValueError, "changed source"):
                module.measure(ROOT, changed, diagnostic=True)
            missing = dict(refs)
            missing["designation"] = {"path": "missing-designation.json", "sha256": "0" * 64}
            with self.assertRaisesRegex(ValueError, "missing source"):
                module.measure(ROOT, missing, diagnostic=True)

    def test_no_activity_transition_shortcut(self):
        refs = json.loads((ROOT / "cases" / "park_at" / "diagnostic-refs.json").read_text())
        activity = json.loads((ROOT / refs["activity"]["path"]).read_text())
        activity["events"].insert(1, {"event": "load", "frame": 350})
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            p = tmp / "activity.json"
            p.write_text(json.dumps(activity) + "\n")
            adjusted = {key: {"path": str((ROOT / value["path"]).resolve()), "sha256": value["sha256"]} for key, value in refs.items()}
            # The original root guard rejects external paths before any measurement.
            adjusted["activity"] = {"path": str(p), "sha256": module.sha(p)}
            with self.assertRaisesRegex(ValueError, "unsafe source"):
                module.measure(ROOT, adjusted, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
