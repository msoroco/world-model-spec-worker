import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit_pair
from prove_comparisons import prove


class ComparisonAuditTests(unittest.TestCase):
    def test_both_saved_original_pairs(self):
        result = prove(ROOT)
        self.assertEqual(set(result["pairs"]), {"roadway_vs_sidewalk", "roadway_vs_shoulder"})
        for pair in result["pairs"].values():
            self.assertTrue(pair["original_lateral_difference_measured"])
            self.assertFalse(pair["physical_acceptance_claimed"])

    def test_resealed_longitudinal_change_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(ROOT / "candidate-corridor.xodr", root / "candidate-corridor.xodr")
            for name in ("roadway_walk", "sidewalk_walk"):
                shutil.copytree(ROOT / "cases" / name, root / "cases" / name)
            history = root / "cases" / "sidewalk_walk" / "diagnostic-body-history.jsonl"
            rows = [json.loads(line) for line in history.read_text().splitlines()]
            rows[1]["body_xy_m"] = [[x+1, y] for x, y in rows[1]["body_xy_m"]]
            history.write_text("".join(json.dumps(row)+"\n" for row in rows))
            manifest = root / "cases" / "sidewalk_walk" / "diagnostic-source-manifest.json"
            packet = json.loads(manifest.read_text())
            packet["body_history"]["sha256"] = hashlib.sha256(history.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(packet))
            first = root / "cases" / "roadway_walk" / "diagnostic-source-manifest.json"
            with self.assertRaisesRegex(ValueError, "longitudinal original bodies"):
                audit_pair(root, first, manifest, declared_band_change=True)

    def test_source_hash_and_declaration_required(self):
        first = ROOT / "cases" / "roadway_walk" / "diagnostic-source-manifest.json"
        second = ROOT / "cases" / "sidewalk_walk" / "diagnostic-source-manifest.json"
        with self.assertRaisesRegex(ValueError, "not declared"):
            audit_pair(ROOT, first, second, declared_band_change=False)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(ROOT / "candidate-corridor.xodr", root / "candidate-corridor.xodr")
            for name in ("roadway_walk", "sidewalk_walk"):
                shutil.copytree(ROOT / "cases" / name, root / "cases" / name)
            history = root / "cases" / "sidewalk_walk" / "diagnostic-body-history.jsonl"
            history.write_text(history.read_text()+"\n")
            a = root / "cases" / "roadway_walk" / "diagnostic-source-manifest.json"
            b = root / "cases" / "sidewalk_walk" / "diagnostic-source-manifest.json"
            with self.assertRaisesRegex(ValueError, "hash differs"):
                audit_pair(root, a, b, declared_band_change=True)


if __name__ == "__main__":
    unittest.main()
