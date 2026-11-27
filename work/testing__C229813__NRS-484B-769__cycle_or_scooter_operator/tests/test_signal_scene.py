"""Exercise reviewed-source gate, right turn and actual arm-actuator calls."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from signal_scene import ASSIGNMENT, SOURCES, construct, load_reviewed_scene


class Adapter:
    def __init__(self, road):
        self.road = road
        self.calls = []
        self.fail_rig = False

    def map_opendrive_bytes(self):
        return self.road

    def route_readback(self, *args):
        self.calls.append("route")
        return True

    def supports_arm_rig(self, *args):
        self.calls.append("rig")
        return not self.fail_rig

    def spawn_cycle(self, *args):
        self.calls.append("cycle")
        return "cycle"

    def spawn_rider(self, *args):
        self.calls.append("rider")
        return "rider"

    def set_cycle_route(self, *args):
        self.calls.append("controller")

    def apply_right_arm_pose(self, *args):
        self.calls.append("arm")
        return True

    def read_right_arm_joints(self, *args):
        self.calls.append("joints")
        return {"shoulder": [0, 0, 1], "elbow": [0, -.3, 1], "wrist": [0, -.6, 1]}

    def destroy(self, actor):
        self.calls.append("destroy:" + actor)


class SceneTest(unittest.TestCase):
    def setUp(self):
        Path(".runtime-work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + "__bicycle_horizontal_right_arm"
        self.scene = {
            "operator_vehicle_kind": "bicycle", "operator_identity": "reviewed rider 1",
            "highway_status": "highway", "roadway_status": "roadway",
            "roadway_polygon": [[-3, -13], [15, -13], [15, 15], [-3, 15]],
            "shoulder_polygon": [[-3, -16], [15, -16], [15, -13], [-3, -13]],
            "right_turn_route": [[0, 0], [10, 0], [10, -10]],
            "rider_arm_rig": {"right_shoulder": "shoulder.R", "right_elbow": "elbow.R",
                              "right_wrist": "wrist.R", "independent_actuation": True,
                              "mount_offset_m": [0, 0, 0.6],
                              "posture_rotations_deg": {name: {bone: [0, 0, 0] for bone in
                                  ("shoulder.R", "elbow.R", "wrist.R")} for name in
                                  ("horizontal_right_arm", "downward_right_arm", "bent_right_arm")}},
            "camera_sites": {name: [0, 0, 3, 0, 0, 0] for name in
                             ("overview", "approach", "reference_corner", "driver_reference")},
            "cycle_blueprint_id": "cycle.reviewed", "rider_blueprint_id": "rider.reviewed"}
        self.packet = {"source_kind": "reviewed_original_scene", "case_id": self.case,
                       "scene": self.scene, "sources": {}}
        for source in SOURCES:
            content = ("road bytes" if source == "map_opendrive" else source).encode()
            path = self.root / source
            path.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            self.scene[source + "_source_sha256"] = digest
            self.packet["sources"][source] = {"path": source, "sha256": digest}
        self.packet_path = self.root / "packet.json"
        self.save()

    def save(self):
        self.packet_path.write_text(json.dumps(self.packet), encoding="utf-8")

    def test_all_nine_exact_kinds_and_postures(self):
        for kind in ("bicycle", "electric_bicycle", "electric_scooter"):
            for posture in ("horizontal_right_arm", "downward_right_arm", "bent_right_arm"):
                self.scene["operator_vehicle_kind"] = kind
                self.packet["case_id"] = ASSIGNMENT + "__" + kind + "_" + posture
                self.save()
                scene, digest = load_reviewed_scene(self.packet_path, self.root,
                                                     self.packet["case_id"])
                self.assertEqual(len(digest), 64)
                adapter = Adapter(b"road bytes")
                built = construct(adapter, scene, self.packet["case_id"])
                self.assertEqual(built["requested_posture"], posture)
                self.assertEqual(adapter.calls,
                                 ["route", "rig", "cycle", "rider", "controller", "arm", "joints"])

    def test_missing_original_source_rejected_before_spawn(self):
        (self.root / "rider_arm_rig").unlink()
        with self.assertRaisesRegex(ValueError, "original source file missing"):
            load_reviewed_scene(self.packet_path, self.root, self.case)

    def test_source_mutation_rejected(self):
        (self.root / "map_opendrive").write_bytes(b"mutated")
        with self.assertRaisesRegex(ValueError, "original source hash differs"):
            load_reviewed_scene(self.packet_path, self.root, self.case)

    def test_unavailable_arm_rig_rejected_without_spawn(self):
        adapter = Adapter(b"road bytes")
        adapter.fail_rig = True
        with self.assertRaisesRegex(ValueError, "rig unavailable"):
            construct(adapter, self.scene, self.case)
        self.assertEqual(adapter.calls, ["route", "rig"])

    def test_wrong_map_rejected_before_spawn(self):
        adapter = Adapter(b"different road")
        with self.assertRaisesRegex(ValueError, "live map differs"):
            construct(adapter, self.scene, self.case)
        self.assertEqual(adapter.calls, [])

    def test_left_turn_route_rejected(self):
        self.scene["right_turn_route"] = [[0, 0], [10, 0], [10, 10]]
        self.save()
        with self.assertRaisesRegex(ValueError, "must turn right"):
            load_reviewed_scene(self.packet_path, self.root, self.case)


if __name__ == "__main__":
    unittest.main()
