"""Selected queue coverage and stale saved-receipt rejection."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from build_gpu_queue import build, digest, local_audit_command  # noqa: E402


class QueueTests(unittest.TestCase):
    def test_current_exact_queue(self):
        queue = build()
        plan = json.loads((HERE / "case-plan.json").read_text())
        self.assertEqual([row["case_id"] for row in queue["cases"]],
                         [row["case_id"] for row in plan["cases"]])
        self.assertEqual([row["order"] for row in queue["cases"]], list(range(1, 14)))
        self.assertEqual(len(queue["comparisons"]), 7)
        for row in queue["cases"]:
            self.assertEqual(set(row["candidate_commands"]),
                             {"fallback1", "fallback2", "fallback3"})
            self.assertIn('"$CARLA_PYTHON"', row["capture_command"])
            self.assertIn("process-saved", row["postprocessing_command"])
            self.assertIn('"$ATTEMPT"', row["additional_source_audit_command"])
            self.assertNotIn(".runtime-work/c111603-", row["additional_source_audit_command"])

    def test_local_audit_rejects_wrong_case_and_preserves_pair(self):
        case = HERE.name + "__clearance_wide"
        manifest = json.loads((HERE / "execution-manifest.json").read_text())
        entry = next(row for row in manifest["cases"] if row["case_id"] == case)
        command = local_audit_command(entry["delivery_acceptance"], case)
        self.assertIn('"$BASELINE_ATTEMPT"', command)
        with self.assertRaisesRegex(ValueError, "selects another case"):
            local_audit_command(entry["delivery_acceptance"], HERE.name + "__other")

    def test_changed_saved_log_rejects_queue(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work") as location:
            folder = Path(location)
            shutil.copyfile(HERE / "execution-manifest.json", folder / "execution-manifest.json")
            shutil.copyfile(HERE / "case-plan.json", folder / "case-plan.json")
            (folder / "aggregate-saved").mkdir()
            shutil.copyfile(HERE / "aggregate-saved/index.json",
                            folder / "aggregate-saved/index.json")
            manifest = json.loads((folder / "execution-manifest.json").read_text())
            for entry in manifest["cases"]:
                for source in [entry, *entry.get("candidates", [])]:
                    shutil.copyfile(HERE / source["construction"], folder / source["construction"])
            index = json.loads((folder / "aggregate-saved/index.json").read_text())
            for row in index["cases"]:
                for key in ("receipt", "log"):
                    shutil.copyfile(HERE / row[key], folder / row[key])
            first_log = folder / index["cases"][0]["log"]
            first_log.write_text(first_log.read_text() + "tampered\n")
            with self.assertRaisesRegex(ValueError, "saved receipt or log changed"):
                build(folder)


if __name__ == "__main__":
    unittest.main()
