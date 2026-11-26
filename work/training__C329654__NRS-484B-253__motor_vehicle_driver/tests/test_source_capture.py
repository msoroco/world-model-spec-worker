import copy
import math
import unittest
from types import SimpleNamespace

from source_capture import sample


def actor(identity, x, y, yaw=0, speed=4, lamp=1):
    class Fake:
        id = identity
        def get_transform(self):
            return SimpleNamespace(location=SimpleNamespace(x=x, y=y), rotation=SimpleNamespace(yaw=yaw))
        def get_velocity(self):
            return SimpleNamespace(x=speed, y=0, z=0)
        def get_light_state(self):
            return lamp
    return Fake()


class SourceCaptureTest(unittest.TestCase):
    def setUp(self):
        self.survey = {"conflict_xy_m": [0, 0], "ego_approach_direction_xy": [1, 0],
                       "opposing_approach_direction_xy": [-1, 0],
                       "turn_start_xy_m": [-2, 0], "turn_end_xy_m": [0, 12],
                       "intersection_polygon_xy_m": [[-4, -4], [4, -4], [4, 4], [-4, 4]],
                       "source_sha256": "a" * 64}
        self.ego, self.initial, self.subsequent = actor(1, -2, 0), actor(2, 10, 0), actor(3, 20, 0)

    def row(self, survey=None, ego=None, initial=None, subsequent=None):
        return sample(100, 100, 5, "case", ego or self.ego, initial or self.initial,
                      subsequent or self.subsequent, survey or self.survey, 1, "synthetic_cpu")

    def test_original_actor_sample(self):
        row = self.row()
        self.assertEqual(row["native_frame"], 100)
        self.assertTrue(row["ego"]["inside_intersection"])
        self.assertTrue(row["ego"]["left_indicator_on"])
        self.assertEqual([o["distance_to_conflict_m"] for o in row["oncoming"]], [10, 20])
        self.assertEqual([o["actor_id"] for o in row["oncoming"]], ["2", "3"])

    def test_original_source_requires_map_and_lane_direction(self):
        with self.assertRaisesRegex(ValueError, "map readback"):
            sample(100, 100, 5, "case", self.ego, self.initial,
                   self.subsequent, self.survey, 1)
        class Map:
            def __init__(self, yaw): self.yaw = yaw
            def get_waypoint(self, location, project_to_road=False):
                return SimpleNamespace(road_id=4, lane_id=-1,
                    transform=SimpleNamespace(rotation=SimpleNamespace(yaw=self.yaw)))
        row = sample(100, 100, 5, "case", self.ego, self.initial,
                     self.subsequent, self.survey, 1, native_map=Map(180))
        self.assertEqual([o["native_road_id"] for o in row["oncoming"]], [4, 4])
        with self.assertRaisesRegex(ValueError, "lane direction differs"):
            sample(100, 100, 5, "case", self.ego, self.initial,
                   self.subsequent, self.survey, 1, native_map=Map(0))

    def test_opposing_lane_rejected(self):
        survey = copy.deepcopy(self.survey)
        survey["opposing_approach_direction_xy"] = [1, 0]
        with self.assertRaisesRegex(ValueError, "not opposite"):
            self.row(survey=survey)

    def test_missing_actor_rejected(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            self.row(subsequent=actor(2, 20, 0))

    def test_absent_lamp_is_measured_absent(self):
        row = self.row(ego=actor(1, -2, 0, lamp=0))
        self.assertFalse(row["ego"]["left_indicator_on"])

    def test_nonfinite_velocity_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite original velocity"):
            self.row(initial=actor(2, 10, 0, speed=math.nan))

    def test_missing_intersection_polygon_rejected(self):
        survey = copy.deepcopy(self.survey)
        del survey["intersection_polygon_xy_m"]
        with self.assertRaisesRegex(ValueError, "surveyed intersection"):
            self.row(survey=survey)

    def test_unsigned_survey_rejected(self):
        survey = copy.deepcopy(self.survey)
        del survey["source_sha256"]
        with self.assertRaisesRegex(ValueError, "source-hashed"):
            self.row(survey=survey)

    def test_frame_drift_rejected(self):
        with self.assertRaisesRegex(ValueError, "frame and time drift"):
            sample(100, 100, 7, "case", self.ego, self.initial,
                   self.subsequent, self.survey, 1, "synthetic_cpu")


if __name__ == "__main__":
    unittest.main()
