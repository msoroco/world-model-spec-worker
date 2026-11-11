"""Material positive and negative checks for unselected saved comparison audit."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

NATIVE = Path(__file__).resolve().parents[1]
ROOT = NATIVE.parent
sys.path.insert(0, str(NATIVE))
from audit_saved_pair import CASES, audit


def receipt(suffix, candidate):
    if candidate == "primary":
        return ROOT / "update015-current-primary" / suffix / "processing.json"
    return ROOT / "update015-current-fallback" / suffix / candidate / "processing.json"


class SavedPairAuditTests(unittest.TestCase):
    def test_all_eight_saved_pairs(self):
        for branch, (reference, contrast) in CASES.items():
            for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
                with self.subTest(branch=branch, candidate=candidate):
                    result = audit(receipt(reference, candidate),
                                   receipt(contrast, candidate), branch, candidate)
                    self.assertTrue(result["passed"])
                    self.assertAlmostEqual(result["observed_crossing_delta_m"], 45.0)

    def test_missing_and_stale_source_rejected(self):
        a = receipt("reference", "primary")
        b = receipt("contrast", "primary")
        with self.assertRaisesRegex(ValueError, "Missing comparison source"):
            audit(a, ROOT / "absent-processing.json", "intersection", "primary")
        changed = json.loads(a.read_text())
        changed["original_source_hashes"]["road.xodr"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "stale.json"
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "stale saved source: road.xodr"):
                audit(path, b, "intersection", "primary")

    def test_changed_fixed_controller_rejected(self):
        original = receipt("contrast", "primary")
        data = json.loads(original.read_text())
        analysis = Path(data["analysis_directory"])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "analysis"
            folder.mkdir()
            for name in data["original_source_hashes"]:
                source = analysis / name
                if source.is_file():
                    target = folder / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(source)
            config = json.loads((analysis / "config.json").read_text())
            config["requested_approach_speed_mps"] = 8.0
            (folder / "config.json").unlink()
            (folder / "config.json").write_text(json.dumps(config))
            data["analysis_directory"] = str(folder)
            data["version"] = str(Path(temp))
            data["original_source_hashes"]["config.json"] = hashlib.sha256(
                (folder / "config.json").read_bytes()).hexdigest()
            altered = folder / "processing.json"
            altered.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "Fixed comparison condition differs"):
                audit(receipt("reference", "primary"), altered,
                      "intersection", "primary")

    def test_changed_declared_difference_rejected(self):
        original = receipt("contrast", "primary")
        data = json.loads(original.read_text())
        analysis = Path(data["analysis_directory"])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "analysis"
            folder.mkdir()
            for name in data["original_source_hashes"]:
                source = analysis / name
                if source.is_file():
                    target = folder / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(source)
            config = json.loads((analysis / "config.json").read_text())
            config["requested_turn_center_x_m"] = -20.0
            (folder / "config.json").unlink()
            (folder / "config.json").write_text(json.dumps(config))
            data["analysis_directory"] = str(folder)
            data["version"] = str(Path(temp))
            data["original_source_hashes"]["config.json"] = hashlib.sha256(
                (folder / "config.json").read_bytes()).hexdigest()
            altered = folder / "processing.json"
            altered.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "Declared crossing-location difference differs"):
                audit(receipt("reference", "primary"), altered,
                      "intersection", "primary")


if __name__ == "__main__":
    unittest.main()
