"""Exact queue ordering and stale construction rejection."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from build_gpu_queue import SAVED_PROOFS, build, digest  # noqa: E402


class QueueTests(unittest.TestCase):
    def copy_sources(self, temporary):
        manifest = json.loads((HERE / "execution-manifest.json").read_text())
        for entry in manifest["cases"]:
            for source in [entry, *entry.get("candidates", [])]:
                path = source["construction"]
                shutil.copyfile(HERE / path, temporary / path)
            proof_name = SAVED_PROOFS[entry["case_id"].rsplit("__", 1)[-1]]
            shutil.copyfile(HERE / proof_name, temporary / proof_name)
            proof = json.loads((temporary / proof_name).read_text())
            shutil.copyfile(HERE / proof["log"], temporary / proof["log"])
        (temporary / "execution-manifest.json").write_text(json.dumps(manifest))
        shutil.copyfile(HERE / "case-plan.json", temporary / "case-plan.json")
        return manifest

    def test_current_queue_covers_selected_cases_and_candidates(self):
        queue = build()
        plan = json.loads((HERE / "case-plan.json").read_text())
        manifest = json.loads((HERE / "execution-manifest.json").read_text())
        self.assertEqual([row["case_id"] for row in queue["cases"]],
                         [row["case_id"] for row in plan["cases"]])
        self.assertEqual([row["order"] for row in queue["cases"]], list(range(1, 10)))
        self.assertEqual(queue["execution_manifest_sha256"], digest(HERE / "execution-manifest.json"))
        for row, entry in zip(queue["cases"], manifest["cases"]):
            self.assertEqual(set(row["candidate_commands"]),
                             {candidate["id"] for candidate in entry["candidates"]})
            self.assertIn("--python \"$CARLA_PYTHON\"", row["capture_command"])
            self.assertIn("process-saved", row["postprocessing_command"])

    def test_changed_construction_rejects_queue(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work") as location:
            temporary = Path(location)
            manifest = self.copy_sources(temporary)
            first = temporary / manifest["cases"][0]["construction"]
            first.write_text(first.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "construction hash changed"):
                build(temporary / "execution-manifest.json", temporary / "case-plan.json")

    def test_stale_saved_proof_rejects_queue(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work") as location:
            temporary = Path(location)
            self.copy_sources(temporary)
            proof_path = temporary / "ending-yields-saved-proof.json"
            proof = json.loads(proof_path.read_text())
            proof["manifest_sha256"] = "0" * 64
            proof_path.write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, "saved proof is stale"):
                build(temporary / "execution-manifest.json", temporary / "case-plan.json")


if __name__ == "__main__":
    unittest.main()
