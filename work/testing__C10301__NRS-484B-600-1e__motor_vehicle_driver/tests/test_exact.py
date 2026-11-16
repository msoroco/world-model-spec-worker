import hashlib, json, pathlib, unittest
from runner import check_config

class ExactConstruction(unittest.TestCase):
    def test_authored_scene_and_case_are_bound(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = check_config(json.loads((root / "config.json").read_text()))
        self.assertEqual(hashlib.sha256((root / config["authored_scene"]).read_bytes()).hexdigest(), config["authored_scene_sha256"])
        self.assertEqual(config["case"]["case_id"], config["selected_case_id"])
        self.assertEqual(config["corridor_context"]["reviewed_road_id"], 1)
        self.assertEqual(config["corridor_context"]["reviewed_lane_id"], -1)

    def test_missing_source_hash_rejected(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text())
        del config["authored_scene_sha256"]
        with self.assertRaisesRegex(ValueError, "OpenDRIVE scene and hash"):
            check_config(config)
