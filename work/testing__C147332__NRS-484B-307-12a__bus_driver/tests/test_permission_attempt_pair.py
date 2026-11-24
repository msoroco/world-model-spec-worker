"""Exact requested permission pair and negative construction binding checks."""
import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from permission_attempt_pair import prove


class PermissionAttemptPairTests(unittest.TestCase):
    def setUp(self):
        self.assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        self.manifest = json.loads((ROOT / "execution-manifest.json").read_text())
        self.raw = {entry["case_id"].rsplit("__", 1)[-1]:
                    (ROOT / entry["construction"]).read_bytes() for entry in self.manifest["cases"]}

    def test_exact_source_bound_pairs(self):
        proof = prove(ROOT, self.assignment)
        self.assertEqual(len(proof["attempts"]), 4)
        self.assertFalse(proof["legal_violation_claimed"])
        self.assertFalse(proof["pinned_compliant_violating_pair_claimed"])
        self.assertFalse(proof["attempts"]["adjacent_dark_drive"]["requested_permission_configuration"])

    def test_source_quote_drift_rejected(self):
        assignment = copy.deepcopy(self.assignment)
        assignment["law"]["text"] = "A green arrow may be visible."
        with self.assertRaisesRegex(ValueError, "source permission"):
            prove(ROOT, assignment)

    def test_construction_sha_drift_rejected(self):
        constructions = dict(self.raw)
        constructions["adjacent_dark_drive"] += b" "
        with self.assertRaisesRegex(ValueError, "construction SHA"):
            prove(ROOT, self.assignment, constructions=constructions)

    def test_relabelled_dark_head_rejected_after_hash_update(self):
        constructions = dict(self.raw)
        kind = "adjacent_dark_drive"
        construction = json.loads(constructions[kind])
        scene_file = next(item for item in construction["files"] if item["path"] == "scene.json")
        scene = json.loads(scene_file["content"])
        next(item for item in scene["signals"] if item["governed_lane_id"] == "west")["display"] = "down_green_arrow"
        scene_file["content"] = json.dumps(scene)
        constructions[kind] = (json.dumps(construction) + "\n").encode()
        manifest = copy.deepcopy(self.manifest)
        from permission_attempt_pair import sha
        next(item for item in manifest["cases"] if item["case_id"].endswith("__" + kind))["construction_sha256"] = sha(constructions[kind])
        with self.assertRaisesRegex(ValueError, "requested attempt differs"):
            prove(ROOT, self.assignment, manifest=manifest, constructions=constructions)


if __name__ == "__main__":
    unittest.main()
