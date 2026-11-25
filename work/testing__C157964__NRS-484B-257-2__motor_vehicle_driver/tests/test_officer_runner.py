import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner
from test_officer_capture_sequence import source_packet


class OfficerRunnerTests(unittest.TestCase):
    def test_staged_other_vehicle_approach(self):
        drive = {"throttle": 0.4, "brake": 0.0, "steer": 0.0}
        self.assertEqual(runner.other_control(359, 600, drive),
                         {"throttle": 0.0, "brake": 1.0, "steer": 0.0})
        self.assertEqual(runner.other_control(360, 600, drive), drive)
        self.assertEqual(runner.other_control(359, 600, drive, 320), drive)
        self.assertEqual(runner.other_control(359, 600, drive, 320.0), drive)
        self.assertEqual(runner.other_control(359, 600, drive, 400),
                         {"throttle": 0.0, "brake": 1.0, "steer": 0.0})
        with self.assertRaisesRegex(ValueError, "release frame outside capture"):
            runner.other_control(359, 600, drive, 600)
        with self.assertRaisesRegex(ValueError, "construction command"):
            runner.other_control(600, 600, drive)

    def test_all_three_exact_configurations_and_changed_site(self):
        original = json.loads((ROOT / "config.json").read_text())
        for suffix in ("officer_controls_go", "officer_controls_hold",
                       "officer_present_inactive"):
            case_id = runner.ASSIGNMENT + "__" + suffix
            config = dict(original, selected_case_id=case_id,
                          case=dict(original["case"], case_id=case_id))
            self.assertEqual(runner.validate_config(config)["selected_case_id"],
                             config["selected_case_id"])
        invalid = json.loads(json.dumps(original))
        invalid["site"]["other_lane"] = [157960, -1]
        with self.assertRaisesRegex(ValueError, "approach lanes differ"):
            runner.validate_config(invalid)
        invalid = json.loads(json.dumps(original))
        invalid["cameras"][0]["width"] = 100
        with self.assertRaisesRegex(ValueError, "capture profile"):
            runner.validate_config(invalid)
        changed = json.loads(json.dumps(original))
        changed["sweep_controls"] = {"ego_target_speed_mps": 3.0,
                                     "other_release_frame": 400.0}
        self.assertEqual(runner.validate_config(changed)["sweep_controls"],
                         changed["sweep_controls"])
        changed["sweep_controls"]["other_release_frame"] = 600
        with self.assertRaisesRegex(ValueError, "release frame"):
            runner.validate_config(changed)
        for case_id in sorted(runner.SWEEP_CASES):
            sweep = json.loads(json.dumps(original))
            sweep["selected_case_id"] = case_id
            sweep["case"]["case_id"] = case_id
            if "__c157964_sub2_judgment_4-" in case_id:
                north = case_id.endswith("0001")
                road = 157966 if north else 157964
                sweep["sweep_controls"] = {"other_approach_road_id": road}
                sweep["site"]["other_lane"] = [road, 1 if north else -1]
                sweep["actor_transforms"]["other"]["location"].update(
                    {"x": -1.8 if north else 1.8, "y": 22.0 if north else -22.0})
                sweep["actor_transforms"]["other"]["rotation"]["yaw"] = -90.0 if north else 90.0
            else:
                sweep["sweep_controls"] = {"other_release_frame": 360.0}
            self.assertEqual(runner.validate_config(sweep)["selected_case_id"], case_id)
            if "__c157964_sub2_judgment_4-" in case_id:
                sweep["site"]["other_lane"] = [157964, -1] if north else [157966, 1]
                with self.assertRaisesRegex(ValueError, "Other approach pose differs"):
                    runner.validate_config(sweep)

    def test_hash_bound_source_copy_and_complete_approach_plan(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            source = root / "source"
            source.mkdir()
            packet = source_packet(source)
            plan = {"format": "worker-officer-approach-construction-plan",
                    "site_id": "CPU-fixture-site",
                    "frames": [{"frame_index": i, "approaching_hazard": False}
                               for i in range(3)]}
            other = source / "other_route.txt"
            other.write_text(json.dumps(plan))
            value = json.loads(packet.read_text())
            value["sources"]["other_route"]["sha256"] = hashlib.sha256(
                other.read_bytes()).hexdigest()
            (source / "source-packet.json").write_text(json.dumps(value))
            output = root / "attempt"
            output.mkdir()
            retained, intake = runner._copy_source_packet(source, output)
            self.assertEqual(intake["site_id"], "CPU-fixture-site")
            self.assertEqual(runner._hazard_plan(
                retained / intake["source_paths"]["other_route"], intake, 3),
                plan["frames"])
            with self.assertRaisesRegex(ValueError, "Reviewed other route differs"):
                runner._hazard_plan(other, intake, 3, 157966)
            plan["other_approach_road_id"] = 157966
            other.write_text(json.dumps(plan))
            self.assertEqual(runner._hazard_plan(other, intake, 3, 157966), plan["frames"])
            plan["frames"][2]["approaching_hazard"] = "unknown"
            other.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "approach plan required"):
                runner._hazard_plan(other, intake, 3)


if __name__ == "__main__":
    unittest.main()
