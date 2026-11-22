"""Check all six requested poses and reject an unbuildable roadway."""
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_pose import REQUESTS, construct
from parking_measurement import measure_frame
from test_parking_measurement import CONTEXT


def context():
    return {**CONTEXT, "reviewed_packet_sha256": "synthetic-source-packet"}


class ParkingPoseTests(unittest.TestCase):
    def test_all_exact_poses_hold_edge_and_footprint_fixed(self):
        poses = {name: construct(context(), name) for name in REQUESTS}
        self.assertEqual(len(poses), 6)
        self.assertEqual({tuple(p["target_center_xy_m"]) for p in poses.values()}, {(0, 2.5)})
        for pose in poses.values():
            observation = measure_frame({"frame": 0, "time_s": 0,
                                         "body_vertices_xy_m": pose["target_body_vertices_xy_m"],
                                         "vehicle_forward_xy": pose["target_forward_xy"]}, context())
            self.assertEqual(observation["body_corners_inside_roadway"], 4)
            self.assertFalse(pose["physical_realization_claimed"])
        self.assertAlmostEqual(poses["park_parallel_lawful"]["target_forward_xy"][0], 1)
        self.assertAlmostEqual(poses["park_parallel_reverse"]["target_forward_xy"][0], -1)
        self.assertGreater(poses["park_angled_lawful"]["target_forward_xy"][1], 0)

    def test_invalid_or_narrow_roadway_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown exact"):
            construct(context(), "park_unknown")
        narrow = context()
        narrow["roadway_polygon_xy_m"] = [[-20, -.2], [20, -.2], [20, 2], [-20, 2]]
        with self.assertRaisesRegex(ValueError, "footprint leaves"):
            construct(narrow, "park_parallel_lawful", edge_offset_m=1)
        with self.assertRaisesRegex(ValueError, "segment missing"):
            construct(context(), "stand_parallel_lawful", segment_index=2)


if __name__ == "__main__":
    unittest.main()
