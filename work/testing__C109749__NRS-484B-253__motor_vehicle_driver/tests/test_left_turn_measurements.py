import importlib.util
import pathlib
import unittest


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "left_turn_measurements.py"
SPEC = importlib.util.spec_from_file_location("left_turn_measurements", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def body(x, y):
    return [[x + dx, y + dy, dz] for dz in (-0.5, 0.5) for dx in (-0.5, 0.5) for dy in (-0.5, 0.5)]


POLYGON = [(-5, -5), (5, -5), (5, 5), (-5, 5)]
MAP_SHA = "a" * 64


def frame(number, *, opponent_x=0, braking=False):
    return {"frame": number, "time_s": number / 20,
            "ego_vertices": body(0, 0), "opponent_vertices": body(opponent_x, 0),
            "ego_heading": (1, 0), "opponent_heading": (-1, 0),
            "ego_speed_mps": 1, "opponent_speed_mps": 5,
            "ego_signal_left": True, "ego_turn_committed": False,
            "opponent_cleared": False, "ego_braking": braking}


class Measurements(unittest.TestCase):
    def test_inside_and_opposing_heading(self):
        measured = MODULE.measure([frame(10)], POLYGON, source_id="original-a", map_sha256=MAP_SHA)
        self.assertTrue(measured["frames"][0]["opponent"]["full_body_inside"])
        self.assertEqual(measured["frames"][0]["heading_cosine"], -1)

    def test_outside_opponent_preserves_ego_occupancy(self):
        measured = MODULE.measure([frame(10, opponent_x=10)], POLYGON, source_id="original-a", map_sha256=MAP_SHA)
        self.assertFalse(measured["frames"][0]["opponent"]["any_vertex_inside"])
        self.assertTrue(measured["frames"][0]["ego"]["full_body_inside"])

    def test_missing_original_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "source-hashed map"):
            MODULE.measure([frame(10)], POLYGON, source_id="", map_sha256=MAP_SHA)

    def test_no_ego_inside_rejected(self):
        sample = frame(10)
        sample["ego_vertices"] = body(10, 10)
        with self.assertRaisesRegex(ValueError, "fully within"):
            MODULE.measure([sample], POLYGON, source_id="original-a", map_sha256=MAP_SHA)

    def test_comparison_requires_observed_difference(self):
        left = MODULE.measure([frame(10)], POLYGON, source_id="original-a", map_sha256=MAP_SHA)
        right = MODULE.measure([frame(10, braking=True)], POLYGON, source_id="original-b", map_sha256=MAP_SHA)
        result = MODULE.compare(left, right, changed_observables=["ego_braking"])
        self.assertEqual(result["legal_judgment"], "unresolved")
        with self.assertRaisesRegex(ValueError, "difference absent"):
            MODULE.compare(left, right, changed_observables=["ego_signal_left"])

    def test_comparison_rejects_map_change(self):
        left = MODULE.measure([frame(10)], POLYGON, source_id="original-a", map_sha256=MAP_SHA)
        right = MODULE.measure([frame(10, braking=True)], POLYGON, source_id="original-b", map_sha256="b" * 64)
        with self.assertRaisesRegex(ValueError, "map differs"):
            MODULE.compare(left, right, changed_observables=["ego_braking"])


if __name__ == "__main__":
    unittest.main()
