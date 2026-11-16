import hashlib, json, pathlib, unittest
from runner import check_config

class ExactConstruction(unittest.TestCase):
    def test_authored_signal_and_case_bound(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = check_config(json.loads((root / "config.json").read_text()))
        self.assertEqual(hashlib.sha256((root / config["authored_scene"]).read_bytes()).hexdigest(), config["authored_scene_sha256"])
        self.assertEqual(config["case"]["case_id"], config["selected_case_id"])
        self.assertEqual(config["posted_limit_value"], 25)
        self.assertIn('signal', (root / "scene.xodr").read_text())

    def test_missing_authority_source_rejected(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text())
        config.pop("authority_source")
        with self.assertRaisesRegex(ValueError, "authority_source"):
            check_config(config)
