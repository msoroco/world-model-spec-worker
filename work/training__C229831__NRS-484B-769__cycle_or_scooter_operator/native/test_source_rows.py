import unittest

from source_rows import CAMERAS, make_rows
from measure_hand_signal import measure


def sources():
    rig = []
    cameras = []
    for frame in range(600):
        right = 100 <= frame < 140
        rig.append({
            "frame": frame, "native_frame": frame + 1000,
            "rider_actor_id": 12, "bicycle_actor_id": 11,
            "bicycle_blueprint": "vehicle.bh.crossbike",
            "bicycle_center_xyz_m": [0.0, 0.0, 0.0], "bicycle_yaw_deg": 0.0,
            "bicycle_body_vertices_xyz_m": [[-.7, -.25, 0.0], [-.7, .25, 0.0],
                                              [.7, .25, 0.0], [.7, -.25, 0.0]],
            "bone_world_xyz_m": {
                "crl_shoulder__R": [0.0, -0.18, 1.4],
                "crl_foreArm__R": [0.0, -0.50 if right else -0.30, 1.4],
                "crl_hand__R": [0.0, -0.80 if right else -0.42, 1.4],
            },
        })
        cameras.append({"frame": frame, "time_s": frame / 20,
                        "camera_names": sorted(CAMERAS),
                        "native_frame": frame + 1000,
                        "pixel_source_ids": {name: f"{name}.mkv#frame={frame}" for name in CAMERAS}})
    return rig, cameras, {
        "source_kind": "original_native_map_and_capture",
        "roadway_polygon_xy_m": [[-2, -2], [2, -2], [2, 2], [-2, 2]],
        "right_turn_route_xy_m": [[-1, 0], [0, 0], [1, 0]],
        "roadway_polygon_source_id": "map-roadway-1",
        "right_turn_route_source_id": "route-1",
        "rider_actor_id": 12, "bicycle_actor_id": 11,
    }


class TestSourceRows(unittest.TestCase):
    def test_original_geometry_into_existing_measurement(self):
        rig, cameras, context = sources()
        rows = make_rows(rig, cameras, context)
        measurement_context = {
            "machine_class": "bicycle", "operator_id": "12",
            "machine_class_source": "original-blueprint",
            "operator_id_source": "original-distinct-rider",
            "roadway_polygon_source": "map-roadway-1",
            "connected_right_turn_route_source": "route-1",
            "keypoint_capture_source": "original-walker-bone-readback",
            "camera_calibration_source": "original-four-view-calibration",
            "derived_channels_used": False,
        }
        measured = measure(rows, measurement_context)
        self.assertTrue(measured["right_arm_extension_observed"])
        self.assertEqual(measured["right_arm_horizontal_rightward_runs"][0]["first_frame"], 100)

    def test_rejects_unsourced_pixels_and_wrong_rider(self):
        rig, cameras, context = sources()
        del cameras[100]["pixel_source_ids"]
        with self.assertRaisesRegex(ValueError, "pixel sources"):
            make_rows(rig, cameras, context)
        rig, cameras, context = sources()
        rig[100]["rider_actor_id"] = 13
        with self.assertRaisesRegex(ValueError, "identity differs"):
            make_rows(rig, cameras, context)
        rig, cameras, context = sources()
        cameras[100]["native_frame"] += 1
        with self.assertRaisesRegex(ValueError, "Native and camera frame join"):
            make_rows(rig, cameras, context)

    def test_geometry_is_derived_not_trusted(self):
        rig, cameras, context = sources()
        context["roadway_polygon_xy_m"] = [[20, 20], [22, 20], [22, 22], [20, 22]]
        rows = make_rows(rig, cameras, context)
        self.assertFalse(any(row["roadway_occupied"] for row in rows))
        rig, cameras, context = sources()
        context["right_turn_route_xy_m"] = [[0, 20], [1, 20]]
        rows = make_rows(rig, cameras, context)
        self.assertFalse(any(row["on_right_turn_route"] for row in rows))
        rig, cameras, context = sources()
        rig[100]["bicycle_body_vertices_xyz_m"][0] = [4.0, 0.0, 0.0]
        rows = make_rows(rig, cameras, context)
        self.assertFalse(rows[100]["roadway_occupied"])


if __name__ == "__main__":
    unittest.main()
