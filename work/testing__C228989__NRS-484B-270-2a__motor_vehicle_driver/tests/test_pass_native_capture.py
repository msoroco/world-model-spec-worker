"""Synthetic adapter checks of frame joins, source receipt and cleanup only."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import pass_native_capture as native
from pass_controller import Observation


def body(y):
    return [[dx, y + dy, z] for z in (-.3, .3)
            for dx in (-.3, .3) for dy in (-.3, .3)]


class Adapter:
    native_attested = True

    def __init__(self, case, packet):
        self.case = case
        self.packet = packet
        self.index = 0
        self.destroyed = []
        self.restored = False
        self.braked = False
        self.missing_camera = False

    def read_context(self, actors):
        return {"case_id": self.case["case_id"], "map_sha256": self.packet["source_refs"][0]["sha256"],
                "ego_kind": "motor_vehicle", "control_kind": "bicycle",
                "ego_driver_source": "original-ego-driver", "control_rider_source": "original-rider",
                "road_origin": [0, 0], "road_forward": [0, 1],
                "lanes": [{"lane_id": "right", "forward": [0, 1], "source_ref": "source-right",
                           "immediate_left_lane_id": "left"},
                          {"lane_id": "left", "forward": [0, 1], "source_ref": "source-left"}],
                "ego_initial_lane_id": "right", "control_initial_lane_id": "right",
                "immediate_left_lane_id": "left", "lane_restrictions_source": "source-rules",
                "left_lane_traffic_source": "source-traffic",
                "left_lane_obstructions_source": "source-obstruction",
                "surrounding_trajectories_source": "source-trajectories"}

    def observe_pass(self, actors):
        return Observation("right", "right", "left", 2, 12.0, 3.0, (), False, False,
                           100 + self.index)

    def apply_pass_control(self, ego, intent, profile):
        if intent["source_frame"] != 100 + self.index:
            raise ValueError("wrong control frame")

    def tick(self, actors):
        frame = 100 + self.index
        self.index += 1
        return {"frame": frame, "time_s": frame / 20}

    def read_pass_row(self, frame, actors):
        return {"origin": "native_world_snapshot", "frame": frame,
                "time_s": frame / 20, "ego_vertices": body(-4 + 4 * (frame - 100)),
                "control_vertices": body(0), "ego_lane_id": "right" if frame == 100 else "left",
                "control_lane_id": "right", "left_lane_occupied_actor_ids": [],
                "ego_speed_mps": 4, "control_speed_mps": 2}

    def read_cameras(self, frame, actors):
        result = {name: {"frame": frame, "time_s": frame / 20,
                         "png": b"\x89PNG\r\n\x1a\n" + bytes([frame % 256])}
                  for name in native.CAMERAS}
        if self.missing_camera:
            del result["driver_reference"]
        return result

    def brake(self):
        self.braked = True

    def destroy(self, actor):
        self.destroyed.append(actor)

    def restore(self):
        self.restored = True


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        plan = json.loads((HERE / "case-plan.json").read_text())
        self.case = next(c for c in plan["cases"] if c["case_id"].endswith("bicycle_open_move_left"))
        map_bytes = b"synthetic map fixture\n"
        self.map_path = self.root / "map.txt"
        self.map_path.write_bytes(map_bytes)
        self.packet = {"control_kind": "bicycle", "immediate_left_lane_id": "left",
                       "source_refs": [{"role": "map", "path": "map.txt",
                                        "sha256": hashlib.sha256(map_bytes).hexdigest()}],
                       "lanes": [{"lane_id": "right"}, {"lane_id": "left"}]}
        self.packet_path = self.root / "synthetic-packet.json"
        self.packet_path.write_text(json.dumps(self.packet) + "\n")
        self.adapter = Adapter(self.case, self.packet)
        self.owned = ["ego-fake", "control-fake"]

    def _construct(self, adapter, packet_path, case):
        return {"actors": {"ego": self.owned[0], "control": self.owned[1]},
                "owned": self.owned, "packet": self.packet}

    def _encode(self, args, **kwargs):
        Path(args[-1]).write_bytes(b"synthetic-video-fixture")

    def test_three_frame_fixture_proves_join_and_receipt(self):
        destination = self.root / "out"
        with patch.object(native, "FRAME_COUNT", 3), \
             patch.object(native, "construct", side_effect=self._construct), \
             patch.object(native.subprocess, "run", side_effect=self._encode):
            receipt = native.capture(self.adapter, self.packet_path, self.case, destination)
        self.assertEqual(receipt["frame_count"], 3)
        self.assertEqual(set(receipt["cameras"]), set(native.CAMERAS))
        self.assertEqual(json.loads((destination / "pass-measurement.json").read_text())
                         ["first_observed_full_pass_frame"], 102)
        self.assertEqual(self.adapter.destroyed, list(reversed(self.owned)))
        self.assertTrue(self.adapter.braked and self.adapter.restored)

    def test_missing_camera_fails_and_removes_attempt(self):
        self.adapter.missing_camera = True
        destination = self.root / "failed"
        with patch.object(native, "FRAME_COUNT", 3), \
             patch.object(native, "construct", side_effect=self._construct):
            with self.assertRaisesRegex(ValueError, "four original cameras"):
                native.capture(self.adapter, self.packet_path, self.case, destination)
        self.assertFalse(destination.exists())
        self.assertTrue(self.adapter.braked and self.adapter.restored)
        self.assertEqual(self.adapter.destroyed, list(reversed(self.owned)))


if __name__ == "__main__":
    unittest.main()
