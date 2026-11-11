import importlib.util
from pathlib import Path
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("visibility_measure", PACKAGE / "visibility_measure.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sample(distance, visible, source):
    return {"distance_m": distance, "visible": visible, "source_ref": source}


class VisibilityMeasureTest(unittest.TestCase):
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
