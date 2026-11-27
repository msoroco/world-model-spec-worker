import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit_selected_comparisons",
                                              ROOT / "audit_selected_comparisons.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def reports():
    rows = {}
    for index in (1, 2, 3):
        case = module.PREFIX + str(index)
        rows[case] = {"case_id": case, "frame_count": 600,
            "source_kind": "original_native_observation",
            "legal_result": None, "expeditiousness": None,
            "stopped_in_alley_frames": 500, "sensor_rest_tolerance_mps": .05,
            "source_sha256": {"site-survey.json": "diagnostic-site"},
            "ordinance_status_source_id": "diagnostic-ordinance",
            "requested_goods_motion": index != 2,
            "requested_idle_after_goods": index == 3,
            "observed_goods_event_ids": [] if index == 2 else ["diagnostic-event"],
            "observed_stopped_after_goods_s": None if index == 2
                                                else 5 if index == 1 else 18}
    return rows


class ComparisonTest(unittest.TestCase):
    def test_source_shaped_controlled_comparison(self):
        result = module.audit(reports())
        self.assertEqual(result["post_goods_idle_difference_s"], 13)
        self.assertIsNone(result["legal_result"])

    def test_site_change_rejected(self):
        values = reports()
        values[module.PREFIX + "3"]["source_sha256"]["site-survey.json"] = "other"
        with self.assertRaisesRegex(ValueError, "fixed site"):
            module.audit(values)

    def test_missing_goods_contrast_rejected(self):
        values = reports()
        values[module.PREFIX + "2"]["observed_goods_event_ids"] = ["unexpected"]
        with self.assertRaisesRegex(ValueError, "goods activity contrast"):
            module.audit(values)

    def test_idle_not_measured_rejected(self):
        values = reports()
        values[module.PREFIX + "3"]["observed_stopped_after_goods_s"] = 5
        with self.assertRaisesRegex(ValueError, "idle difference missing"):
            module.audit(values)


if __name__ == "__main__":
    unittest.main()
