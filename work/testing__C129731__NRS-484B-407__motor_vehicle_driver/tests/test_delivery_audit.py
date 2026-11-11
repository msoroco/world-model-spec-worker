"""Small source-shaped tests for the independent Native delivery audit."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location("c129731_delivery_audit", HERE / "delivery_audit.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = ROOT / ".runtime-work/c129731-rebound-crest-at-compat-v1"
CASE = "testing__C129731__NRS-484B-407__motor_vehicle_driver__crest__at_500ft"


class DeliveryAuditSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name)
        names = ("video_frames.jsonl", "motion_history.jsonl", "trace.jsonl",
                 "capture/evidence.jsonl", "turn_history.jsonl")
        for name in names:
            rows = [json.loads(line) for line in (SOURCE / name).open().readlines()[:3]]
            if name == "capture/evidence.jsonl":
                motion = [json.loads(line) for line in (SOURCE / "motion_history.jsonl").open().readlines()[:3]]
                for ray, m in zip(rows, motion):
                    sample = ray["original_observations"]["participants"][0]
                    for index, direction in enumerate(("approach_a", "approach_b"), start=1):
                        other = m["approaches"][direction]
                        person = dict(sample, actor_id=100 + index + 1,
                                      position_m=other["location_xyz_m"], velocity_mps=other["velocity_xyz_mps"])
                        ray["original_observations"]["participants"].append(person)
            path = self.attempt / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        config = json.loads((SOURCE / "config.json").read_text())
        config["duration_s"] = .15
        (self.attempt / "config.json").write_text(json.dumps(config))
        site = config["site_source"]["path"]
        (self.attempt / site).write_bytes((SOURCE / site).read_bytes())

    def test_three_source_frames_and_all_participants(self):
        report = MODULE.validate_originals(self.attempt, CASE, 3)
        self.assertEqual(report["frames"], 3)
        self.assertEqual(set(report["participant_ids"]), {101, 102, 103})

    def test_missing_approach_participant_rejected(self):
        path = self.attempt / "capture/evidence.jsonl"
        rays = MODULE.rows(path)
        rays[1]["original_observations"]["participants"].pop()
        path.write_text("".join(json.dumps(row) + "\n" for row in rays))
        with self.assertRaisesRegex(ValueError, "participant inventory"):
            MODULE.validate_originals(self.attempt, CASE, 3)

    def test_missing_two_direction_rays_rejected(self):
        path = self.attempt / "capture/evidence.jsonl"
        rays = MODULE.rows(path)
        rays[1]["visibility"]["approaches"].pop()
        path.write_text("".join(json.dumps(row) + "\n" for row in rays))
        with self.assertRaisesRegex(ValueError, "two-direction ray"):
            MODULE.validate_originals(self.attempt, CASE, 3)

    def test_unreviewed_pixel_box_rejected(self):
        inspect, finish = MODULE.review_checker([{"video_frame": 1, "bbox_xyxy": [0, 0, 3, 3]}], 3, 3)
        with self.assertRaisesRegex(ValueError, "not decoded"):
            finish()

    def test_diagnostic_result_cannot_be_delivery(self):
        (self.attempt / "result.json").write_bytes((SOURCE / "result.json").read_bytes())
        with self.assertRaisesRegex(ValueError, "Native non-diagnostic result required"):
            MODULE.audit(self.attempt, CASE, "job", 1, "recording", self.attempt / "review.json",
                         self.attempt / "audit.json", Path(self.temp.name).parent / "decode-receipt.json")


if __name__ == "__main__":
    unittest.main()
