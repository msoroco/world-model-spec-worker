import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from runner import stage
from test_center_lane_site import packet


class RunnerTests(unittest.TestCase):
    def test_stage_reviewed_site_and_pre_entry_intent(self):
        scratch = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ".runtime-work/c382162-owner"))
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            root = Path(tmp)
            source = root / "reviewed"
            source.mkdir()
            for name, data in (("map.json", {"opendrive_sha256": "a"}),
                               ("highway.json", {"public_highway_confirmed": True})):
                (source / name).write_text(json.dumps(data) + "\n")
            site = packet()
            site["native_map_source"] = {"path": "map.json", "sha256": hashlib.sha256((source / "map.json").read_bytes()).hexdigest()}
            site["highway_review_source"] = {"path": "highway.json", "sha256": hashlib.sha256((source / "highway.json").read_bytes()).hexdigest()}
            site_path = source / "site.json"
            site_path.write_text(json.dumps(site) + "\n")
            intent = source / "intent.json"
            intent.write_text(json.dumps({"source_ref": "pre-entry-intent.json"}) + "\n")
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            staged, binding = stage(site_path, digest(site_path), intent,
                                    digest(intent), root / "attempt")
            self.assertEqual(staged["route"]["center_lane_id"], "C")
            self.assertEqual(binding["sha256"], digest(root / "attempt/pre-entry-intent.json"))
            with self.assertRaisesRegex(ValueError, "already populated"):
                stage(site_path, digest(site_path), intent, digest(intent), root / "attempt")


if __name__ == "__main__":
    unittest.main()
