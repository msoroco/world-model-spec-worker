import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plan = load("motion_plan")
site = load("site_source")


class PlanTests(unittest.TestCase):
    def test_exact_site_and_comparison_plan(self):
        result = plan.validate(ROOT, site.inventory)
        self.assertEqual(len(result["case_ids"]), 6)
        self.assertFalse(result["physical_motion_verified"])

    def test_changed_site_hash_or_fixed_motion_rejected(self):
        original = json.loads((ROOT / "motion-plan.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            temporary = Path(tmp)
            for name in ("signal-site.xodr", "stop-site.xodr", "visible-site.xodr"):
                (temporary / name).write_bytes((ROOT / name).read_bytes())
            changed = copy.deepcopy(original)
            changed["cases"][0]["site_sha256"] = "0"*64
            (temporary / "motion-plan.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "source hash"):
                plan.validate(temporary, site.inventory)
            changed = copy.deepcopy(original)
            changed["cases"][0]["ego_hold_ticks"] += 1
            (temporary / "motion-plan.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "changed motion"):
                plan.validate(temporary, site.inventory)


if __name__ == "__main__":
    unittest.main()
