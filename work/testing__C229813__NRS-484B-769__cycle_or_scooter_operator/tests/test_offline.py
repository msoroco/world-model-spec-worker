import json
import unittest
from pathlib import Path
from signal_scene import case_parts, requested_pose

class ExactOffline(unittest.TestCase):
    def test_selected_case_and_pose(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/"config.json").read_text())
        kind,posture=case_parts(config["selected_case_id"])
        self.assertEqual(kind,config["case"]["operator_vehicle_kind"])
        self.assertEqual(posture,config["case"]["posture_key"])
        self.assertIn("wrist",requested_pose(posture))

if __name__=="__main__":unittest.main()
