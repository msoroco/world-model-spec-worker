import importlib.util
from pathlib import Path
import sys
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parents[1] / "runtime" / "scenario_pipeline"))
SPEC = importlib.util.spec_from_file_location("visibility_measure", PACKAGE / "visibility_measure.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sample(distance, visible, source):
    return {"distance_m": distance, "visible": visible, "source_ref": source}


class VisibilityMeasureTest(unittest.TestCase):
    def test_pinned_native_proxy_keeps_both_directions_and_censoring(self):
        from traffic_spec_adapter.visibility import CONVENTION
        value = {"visibility_criterion": "any_of_nine_body_samples",
                 "distance_convention": CONVENTION, "eye_height_m": 1.4,
                 "scan_step_m": 10, "horizon_tolerance_m": .25,
                 "probe_distance_m": 152.4,
                 "ego_body_samples_m": [[float(i), 0., 1.] for i in range(9)],
                 "required_lane_ids": [-1, 1],
                 "approaches": [
                     {"lane_id": -1, "any_sample_clear_at_probe": False,
                      "any_body_sight_horizon": {"bound": "first_sampled_occlusion",
                                                 "bracket_m": [150., 150.125]}},
                     {"lane_id": 1, "any_sample_clear_at_probe": True,
                      "any_body_sight_horizon": {"bound": "at_least", "distance_m": 230.}}]}
        report = MODULE.summarize_native_frame(value, "a" * 64, [-1, 1])
        self.assertEqual(report["pinned_proxy_m"], 150.)
        self.assertEqual(report["incoming_approaches"][1]["bounds_m"], [230., None])
        self.assertIsNone(report["legal_visibility_judgment"])
        value["approaches"].pop()
        with self.assertRaisesRegex(ValueError, "Both sourced incoming"):
            MODULE.summarize_native_frame(value, "a" * 64, [-1, 1])

    def test_requires_both_directions(self):
        with self.assertRaisesRegex(ValueError, "both inventoried"):
            MODULE.summarize({"approach_a": [sample(160, True, "a")]})

    def test_preserves_obstruction_bracket_and_exact_boundary(self):
        report = MODULE.summarize({
            "approach_a": [sample(140, True, "a1"), sample(150, False, "a2"),
                           sample(152.4, False, "a3")],
            "approach_b": [sample(140, True, "b1"), sample(152.4, True, "b2")],
        })
        self.assertEqual(report["statutory_distance_m"], 152.4)
        self.assertEqual(report["directions"]["approach_a"]["nearest_observed_blockage_m"], 150)
        self.assertTrue(report["directions"]["approach_a"]["has_sample_at_or_beyond_500ft"])
        self.assertIsNone(report["directions"]["approach_b"]["nearest_observed_blockage_m"])

    def test_censors_short_inventory(self):
        report = MODULE.summarize({
            "approach_a": [sample(120, True, "a")],
            "approach_b": [sample(160, True, "b")],
        })
        self.assertFalse(report["directions"]["approach_a"]["has_sample_at_or_beyond_500ft"])


if __name__ == "__main__":
    unittest.main()
