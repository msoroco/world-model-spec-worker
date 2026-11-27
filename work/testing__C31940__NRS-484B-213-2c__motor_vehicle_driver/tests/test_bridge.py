"""Focused bridge boundary, source and case validation tests."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_measure import measure
from native_scene import ASSIGNMENT, validate
from source_bind import bind


def frame(front, left=0.5, index=0):
    return {"original_frame": index, "time_s": (index+1)*0.05,
            "actors": {"ego": {"front_station_m": front, "rear_station_m": front-4,
                               "station_m": front-2, "centerline_signed_body_edge_m": left}},
            "left_side_rays": [{"clear_distance_m": 8, "censored": False,
                                "hit_kind": "opaque_obstacle"}]}


class BridgeTests(unittest.TestCase):
    def road(self, one_way=False):
        return {"structure_type": "bridge", "bridge_entrance_station_m": 100,
                "one_way_highway": one_way, "centerline_source_sha256": "c",
                "bridge_source_sha256": "b", "public_highway": True,
                "lanes": [{"lane_id": "forward", "direction": 1}] +
                         ([] if one_way else [{"lane_id": "reverse", "direction": -1}]),
                "forward_unit_xy": [1, 0], "centerline_origin_xy": [0, 0]}

    def test_exact_100_foot_boundary_and_body_references(self):
        entrance = 100
        distances = [30.7848, 30.48, 30.1752]
        rows = [frame(entrance-gap, index=i) for i, gap in enumerate(distances)]
        result = measure({"road": self.road(), "frames": rows})
        got = result["per_frame"]
        self.assertEqual([row["within_100ft_front_reference"] for row in got],
                         [False, True, True])
        self.assertEqual([round(row["bridge_distance_front_m"], 4) for row in got], distances)
        self.assertTrue(all(row["bridge_distance_rear_m"] > row["bridge_distance_front_m"] for row in got))
        self.assertEqual(result["legal_result"], "unresolved")

    def test_missing_observation_rejected(self):
        row = frame(70)
        del row["left_side_rays"]
        with self.assertRaisesRegex(ValueError, "original view rays"):
            measure({"road": self.road(), "frames": [row]})

    def test_one_way_case_requires_one_way_source(self):
        case = ASSIGNMENT + "__one_way_exception"
        packet = {"case_id": case, "law_id": "NRS-484B-213-2c", "cell_id": "C31940",
                  "actor": "motor_vehicle_driver", "reviewed": True, "reviewer": "test",
                  "review_source_sha256": "review", "map_opendrive_sha256": "map",
                  "fps": 20, "duration_s": 45, "road": self.road(False)}
        with self.assertRaisesRegex(ValueError, "case highway direction mismatch"):
            validate(packet, case)

    def test_source_binding_rejects_changed_bridge(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            roles = ["map", "highway", "centerline", "lane_forward", "lane_reverse",
                     "ego_vehicle", "bridge", "bridge_entrance", "view_geometry", "camera_plan"]
            entries = []
            for role in roles:
                file = root / role
                file.write_text(role)
                entries.append({"role": role, "path": role,
                                "sha256": hashlib.sha256(role.encode()).hexdigest()})
            packet = {"sources": entries,
                      "map_opendrive_sha256": next(e["sha256"] for e in entries if e["role"] == "map"),
                      "road": {"one_way_highway": False,
                               "centerline_source_sha256": next(e["sha256"] for e in entries if e["role"] == "centerline"),
                               "bridge_source_sha256": next(e["sha256"] for e in entries if e["role"] == "bridge")}}
            self.assertIn("bridge", bind(packet, root))
            (root / "bridge").write_text("changed")
            with self.assertRaisesRegex(ValueError, "source bytes changed"):
                bind(packet, root)


if __name__ == "__main__":
    unittest.main()
