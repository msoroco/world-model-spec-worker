import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("comparison_audit", ROOT / "comparison_audit.py")
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


def receipt(policy, delay):
    return {"format": "worker-delivery-audit", "passed": True,
            "case_id": ROOT.name + "__" + policy,
            "law_id": "NRS-484B-280-1c", "cell_id": "C233871",
            "actor_id": "motor_vehicle_driver", "map_sha256": "map",
            "road_site_sha256": "road", "fixed_scene_sha256": "scene",
            "participant_classes": ["motor_vehicle", "pedestrian"],
            "camera_contract_sha256": "cameras", "duration_s": 30,
            "response_policy": policy,
            "measurement": {"format": "worker-on-road-pedestrian-measurements",
                            "frame_count": 9, "first_observation": {"frame": 102},
                            "observed_response_delay_s": delay,
                            "legal_proper_caution_verdict": "unresolved",
                            "sources": {name: "source" for name in
                                        ("road-site.json", "map.xodr", "encounter-history.jsonl",
                                         "video_frames.jsonl")}},
            "native_result_sha256": "result", "frame_count": 9,
            "frame_map_sha256": "mapframes", "video_sha256": "video",
            "source_decode_receipt_sha256": "decode",
            "human_observation_claimed": False, "legal_verdict": None}


class ComparisonTests(unittest.TestCase):
    def test_measured_difference_and_fixed_conditions(self):
        prompt = receipt("prompt_brake", 0)
        deferred = receipt("deferred_brake", .15)
        self.assertTrue(comparison.audit(prompt, deferred)["passed"])
        altered = copy.deepcopy(deferred)
        altered["map_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "fixed condition differs"):
            comparison.audit(prompt, altered)
        altered = copy.deepcopy(deferred)
        altered["measurement"]["observed_response_delay_s"] = 0
        with self.assertRaisesRegex(ValueError, "not physically observed"):
            comparison.audit(prompt, altered)

    def test_rejects_legal_or_human_claim_and_missing_source(self):
        prompt = receipt("prompt_brake", 0)
        deferred = receipt("deferred_brake", .15)
        for field, value, error in (("legal_verdict", "proper", "legal"),
                                    ("human_observation_claimed", True, "human")):
            altered = copy.deepcopy(deferred)
            altered[field] = value
            with self.assertRaisesRegex(ValueError, error):
                comparison.audit(prompt, altered)
        altered = copy.deepcopy(deferred)
        altered["measurement"]["sources"].pop("map.xodr")
        with self.assertRaisesRegex(ValueError, "source-bound"):
            comparison.audit(prompt, altered)


if __name__ == "__main__":
    unittest.main()
