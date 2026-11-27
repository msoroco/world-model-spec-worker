import hashlib
import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("comparison_audit", ROOT / "comparison_audit.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ComparisonTests(unittest.TestCase):
    def test_all_exact_pairs_and_source_negatives(self):
        plan_path = ROOT / "case-plan.json"
        plan = json.loads(plan_path.read_text())
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as tmp:
            root = Path(tmp)
            attempts = {}
            for case in plan["cases"]:
                suffix = case["case_id"].rsplit("__", 1)[1]
                directory = root / suffix
                directory.mkdir()
                design = case["design"]
                source_hashes = {}
                for name, value in {
                    "context": "same original street/timezone source",
                    "classification": design["vehicle_class"],
                    "activity": design["purpose"],
                    "trace": suffix,
                    "frame_map": suffix,
                }.items():
                    path = directory / (name + ".txt")
                    path.write_text(str(value) + "\n")
                    source_hashes[name] = digest(path)
                manifest = {"format": "night-parking-original-sources-v1", "sources": {
                    name: {"path": name + ".txt", "sha256": sha} for name, sha in source_hashes.items()}}
                (directory / "night-parking-sources.json").write_text(json.dumps(manifest) + "\n")
                elapsed = design["duration_s"]
                overlap = elapsed
                if suffix == "outside_window_30m01s":
                    overlap = 0
                elif suffix == "boundary_01m":
                    overlap = 1800
                elif suffix == "boundary_06m":
                    overlap = 1
                body = [[0, 0], [1, 0], [1, 1], [0, 1]]
                start = dt.datetime.fromisoformat("2026-11-27T" + design["start_local"] + "-08:00")
                end = start + dt.timedelta(seconds=elapsed)
                measured = {"source_hashes": source_hashes, "subject_body_start_xy_m": body,
                            "other_vehicle_body_start_xy_m": [[5, 0], [6, 0], [6, 1], [5, 1]],
                            "elapsed_s": elapsed, "night_overlap_s": overlap,
                            "start_local": start.isoformat(), "end_local": end.isoformat(),
                            "self_propelled": design["vehicle_class"] == "motor",
                            "activity": design["purpose"]}
                (directory / "result.json").write_text(json.dumps({"case_id": case["case_id"],
                    "physical_acceptance_claimed": False, "measured_values": measured}) + "\n")
                attempts[case["case_id"]] = directory
            for comparison in plan["comparisons"]:
                receipt = MODULE.audit(plan_path, comparison["comparison_id"], [attempts[cid] for cid in comparison["case_ids"]])
                self.assertTrue(receipt["passed"])
            first = attempts[plan["comparisons"][0]["case_ids"][0]]
            (first / "context.txt").write_text("changed original source\n")
            with self.assertRaisesRegex(ValueError, "stale original comparison source"):
                MODULE.audit(plan_path, plan["comparisons"][0]["comparison_id"], [attempts[cid] for cid in plan["comparisons"][0]["case_ids"]])
            (first / "result.json").unlink()
            with self.assertRaisesRegex(ValueError, "missing saved exact result"):
                MODULE.audit(plan_path, plan["comparisons"][0]["comparison_id"], [attempts[cid] for cid in plan["comparisons"][0]["case_ids"]])


if __name__ == "__main__":
    unittest.main()
