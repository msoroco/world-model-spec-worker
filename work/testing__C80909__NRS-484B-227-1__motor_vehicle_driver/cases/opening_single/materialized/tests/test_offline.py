import hashlib, json, unittest
from pathlib import Path
from runner import check_scene

class OfflineCase(unittest.TestCase):
    def test_source_bound_scene(self):
        scene=json.loads(Path("scene.json").read_text())
        check_scene(scene)
        self.assertEqual(hashlib.sha256(Path("road.xodr").read_bytes()).hexdigest(),scene["context"]["map_source_sha256"])
        self.assertEqual(hashlib.sha256(Path("reviewed-median-context.json").read_bytes()).hexdigest(),scene["reviewed_context_sha256"])
        self.assertEqual(hashlib.sha256(Path("authority-review-source.json").read_bytes()).hexdigest(),scene["context"]["authority_review_source_sha256"])
