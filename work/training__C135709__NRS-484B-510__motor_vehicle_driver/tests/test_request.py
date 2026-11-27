import json
import unittest
from pathlib import Path
from capture_plan import AID, build
from runner import check


class ExactRestrictedZoneRequest(unittest.TestCase):
    def test_materialized_request(self):
        config = json.loads(Path("config.json").read_text())
        case_id = config["case_id"]
        request = build(case_id[len(AID) + 2:],
                        approach_speed_cap_mps=config["approach_speed_cap_mps"])
        self.assertEqual(check(request)["case_id"], case_id)
        self.assertEqual(config["camera_sizes"], {name: list(size) for name, size in request["camera_sizes"].items()})
        self.assertEqual(config["frames"], 600)
        self.assertIn(config["approach_speed_cap_mps"], (3.0, 4.0))
        self.assertFalse(config["physical_acceptance_claimed"])
        request["duration_s"] = 10
        with self.assertRaisesRegex(ValueError, "differs"):
            check(request)
