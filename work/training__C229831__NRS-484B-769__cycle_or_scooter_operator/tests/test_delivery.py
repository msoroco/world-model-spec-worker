"""Check independent selected-case source and comparison audits."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
SCRATCH = REPO / ".runtime-work/c229831-temp"
SPEC = importlib.util.spec_from_file_location("c229831_delivery", FOLDER / "delivery_acceptance.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
COMP = importlib.util.spec_from_file_location("c229831_comparison", FOLDER / "comparison_audit.py")
COMPARISON = importlib.util.module_from_spec(COMP)
COMP.loader.exec_module(COMPARISON)


class DeliveryEvidenceTest(unittest.TestCase):
    def test_source_and_pixel_decode(self):
        for label in "abc":
            case = FOLDER.name + "__probe_" + label
            report = MODULE.audit(SCRATCH / f"compat-{label}-primary-v2", case, True)
            self.assertEqual(report["frames"], 600)
            self.assertEqual(len([name for name in report["source_hashes"] if name.endswith(".mkv")]), 4)
            self.assertFalse(report["physical_acceptance"])

    def test_missing_arm_source_rejected(self):
        source = SCRATCH / "compat-a-primary-v2"
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            target = Path(temp)
            for path in source.iterdir():
                if path.name != "rider_arm.jsonl":
                    (target / path.name).symlink_to(path.resolve(), target_is_directory=path.is_dir())
            with self.assertRaisesRegex(ValueError, "Missing delivery source: rider_arm.jsonl"):
                MODULE.audit(target, FOLDER.name + "__probe_a", True)

    def test_comparison_fixed_conditions(self):
        report = COMPARISON.audit(
            SCRATCH / "compat-a-primary-v2", SCRATCH / "compat-c-primary-v2",
            FOLDER.name + "__probe_a", FOLDER.name + "__probe_c",
            FOLDER.name + "__general_vs_exception")
        self.assertEqual(report["measured_methods"], ["right_horizontal", "left_upward"])
        self.assertIsNone(report["legal_verdict"])


if __name__ == "__main__":
    unittest.main()
