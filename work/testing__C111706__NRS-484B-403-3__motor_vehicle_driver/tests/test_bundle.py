import json, unittest
from pathlib import Path
import runner

class BundleTest(unittest.TestCase):
    def test_exact_identity_and_four_view_timebase(self):
        self.assertEqual(runner.check(), json.loads(Path("config.json").read_text())["selected_case_id"])
    def test_selected_case_and_channel_inventory(self):
        config=json.loads(Path("config.json").read_text())
        self.assertEqual(config["frame_count"],900)
        self.assertEqual(len(config["cameras"]),4)
        self.assertEqual(len(config["case"]["recording_description"]["channels"]),5)

if __name__ == "__main__": unittest.main()
