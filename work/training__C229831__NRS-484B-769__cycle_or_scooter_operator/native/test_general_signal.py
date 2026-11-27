import unittest

from measure_general_signal import measure_left_upward


def rows(upward):
    result = []
    for frame in range(600):
        active = upward and 100 <= frame < 140
        result.append({
            "frame": frame, "time_s": frame / 20, "rider_actor_id": 12,
            "bicycle_actor_id": 11, "bicycle_blueprint": "vehicle.bh.crossbike",
            "bicycle_yaw_deg": 0, "requested_method": "left_upward" if active else "none",
            "roadway_occupied": True, "on_right_turn_route": 80 <= frame < 250,
            "bone_world_xyz_m": {
                "crl_shoulder__L": [0.0, 0.0, 1.4],
                "crl_foreArm__L": [0.0, 0.12 if active else 0.04,
                                    1.6 if active else 1.3],
                "crl_hand__L": [0.0, 0.3 if active else 0.08,
                                1.9 if active else 1.2],
            },
        })
    return result


PACKET = {"kind": "original_native_arm_readback", "rider_actor_id": 12,
          "bicycle_actor_id": 11}


class TestGeneralSignal(unittest.TestCase):
    def test_three_dimensional_left_upward_and_no_signal(self):
        yes = measure_left_upward(rows(True), rider_id=12, bicycle_id=11,
                                  source_packet=PACKET)
        no = measure_left_upward(rows(False), rider_id=12, bicycle_id=11,
                                 source_packet=PACKET)
        self.assertEqual(yes["left_arm_upward_frames"], list(range(100, 140)))
        self.assertFalse(no["left_arm_upward_observed"])
        self.assertIsNone(yes["NRS_484B_420_method_conclusion"])

    def test_rejects_missing_bone_and_identity_and_source(self):
        sample = rows(True)
        del sample[100]["bone_world_xyz_m"]["crl_hand__L"]
        with self.assertRaisesRegex(ValueError, "world bone position"):
            measure_left_upward(sample, rider_id=12, bicycle_id=11, source_packet=PACKET)
        with self.assertRaisesRegex(ValueError, "source identities"):
            measure_left_upward(rows(True), rider_id=12, bicycle_id=13, source_packet=PACKET)
        with self.assertRaisesRegex(ValueError, "Original 600-frame"):
            measure_left_upward(rows(True), rider_id=12, bicycle_id=11,
                                source_packet={"kind": "derived_pose"})

    def test_rejects_time_and_roadway_omission(self):
        sample = rows(True)
        sample[120]["time_s"] += 0.05
        with self.assertRaisesRegex(ValueError, "time join"):
            measure_left_upward(sample, rider_id=12, bicycle_id=11, source_packet=PACKET)
        sample = rows(True)
        del sample[120]["roadway_occupied"]
        with self.assertRaisesRegex(ValueError, "roadway or route"):
            measure_left_upward(sample, rider_id=12, bicycle_id=11, source_packet=PACKET)


if __name__ == "__main__":
    unittest.main()
