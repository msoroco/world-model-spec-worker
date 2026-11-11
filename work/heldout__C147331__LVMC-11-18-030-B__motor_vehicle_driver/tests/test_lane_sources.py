import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lane_measurement import measure_saved_sources
from lane_sources import LaneSourceRecorder, marked_lane_slice


class Box:
    def get_world_vertices(self, transform):
        x = transform.location.x
        return [NS(x=x + dx, y=dy, z=z)
                for z in (0, 2) for dx, dy in ((-0.5, -0.5), (0.5, -0.5),
                                                  (0.5, 0.5), (-0.5, 0.5))]


class Actor:
    def __init__(self, actor_id, x=0):
        self.id = actor_id
        self.x = x
        self.bounding_box = Box()

    def get_transform(self):
        return NS(location=NS(x=self.x))

    def get_velocity(self):
        return NS(x=2, y=0)


def waypoint(reverse=False):
    transform = NS(location=NS(x=0, y=0),
                   get_forward_vector=lambda: NS(x=-1 if reverse else 1, y=0))
    return NS(transform=transform, lane_width=3, lane_id=4, road_id=9,
              left_lane_marking=NS(type="Solid"),
              right_lane_marking=NS(type="Broken"))


class NativeLaneSourcesTest(unittest.TestCase):
    def test_both_directions_and_markings(self):
        for reverse in (False, True):
            lane = marked_lane_slice(waypoint(reverse))
            self.assertEqual(lane["lane_id"], 4)
            self.assertEqual(lane["left_marking"], "Solid")
            self.assertEqual(len(lane["polygon_xy_m"]), 4)
        w = waypoint()
        w.left_lane_marking = None
        with self.assertRaisesRegex(ValueError, "markings missing"):
            marked_lane_slice(w)
        w.left_lane_marking = NS(type="LaneMarkingType.NONE")
        with self.assertRaisesRegex(ValueError, "Unmarked"):
            marked_lane_slice(w)

    def test_retained_source_measurement_and_rejections(self):
        with tempfile.TemporaryDirectory() as tmp:
            ego, other = Actor(1), Actor(2, 4)
            with LaneSourceRecorder(tmp, ego, overtaken=other) as recorder:
                recorder.append(10, 0.5, waypoint())
                ego.x = 0.2
                recorder.append(11, 0.55, waypoint())
                with self.assertRaisesRegex(ValueError, "Missing or unordered"):
                    recorder.append(13, 0.6, waypoint())
            measured = measure_saved_sources(Path(tmp) / "marked_lane_sources.jsonl",
                                             expected_ego_id=1, require_overtaken=True)
            self.assertEqual(len(measured["frames"]), 2)
            self.assertTrue(all(row["full_footprint_inside"] for row in measured["frames"]))
            self.assertFalse(measured["measured_order_reversal"])
            with self.assertRaisesRegex(ValueError, "identity changed"):
                measure_saved_sources(recorder.path, expected_ego_id=3)
            rows = [json.loads(line) for line in recorder.path.read_text().splitlines()]
            rows[1]["overtaken_id"] = 3
            recorder.path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            with self.assertRaisesRegex(ValueError, "identity changed"):
                measure_saved_sources(recorder.path, expected_ego_id=1,
                                      require_overtaken=True)
            rows[1]["overtaken_id"] = 2
            rows[1]["frame"] = 12
            recorder.path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            with self.assertRaisesRegex(ValueError, "Missing or unordered"):
                measure_saved_sources(recorder.path, expected_ego_id=1)

    def test_missing_passing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with LaneSourceRecorder(tmp, Actor(1)) as recorder:
                recorder.append(0, 0.0, waypoint())
            with self.assertRaisesRegex(ValueError, "Passing participant source missing"):
                measure_saved_sources(recorder.path, expected_ego_id=1,
                                      require_overtaken=True)

    def test_measured_passing_order_reversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            ego, other = Actor(1, 0), Actor(2, 4)
            with LaneSourceRecorder(tmp, ego, overtaken=other) as recorder:
                recorder.append(0, 0.0, waypoint())
                ego.x = 5
                recorder.append(1, 0.05, waypoint())
            measured = measure_saved_sources(recorder.path, expected_ego_id=1,
                                             require_overtaken=True)
            self.assertTrue(measured["measured_order_reversal"])
            self.assertLess(measured["frames"][0]["ego_minus_other_longitudinal_m"], 0)
            self.assertGreater(measured["frames"][1]["ego_minus_other_longitudinal_m"], 0)


if __name__ == "__main__":
    unittest.main()
