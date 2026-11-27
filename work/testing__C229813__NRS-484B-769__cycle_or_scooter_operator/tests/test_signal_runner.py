"""Exercise 900-frame original acquisition and fail-closed arm readback."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import FRAMES, VIEWS, run
from signal_scene import ASSIGNMENT, SOURCES
from signal_measurements import measure
from analysis import analyze


class Adapter:
    def __init__(self, source):
        self.source = source
        self.frames = 0
        self.destroyed = []
        self.missing_arm = False

    def map_opendrive_bytes(self):
        return self.source

    def route_readback(self, *args):
        return True

    def supports_arm_rig(self, *args):
        return True

    def spawn_cycle(self, *args):
        return "cycle"

    def spawn_rider(self, *args):
        return "rider"

    def set_cycle_route(self, *args):
        pass

    def apply_right_arm_pose(self, *args):
        return True

    def read_right_arm_joints(self, *args):
        return {"shoulder": [0, 0, 1], "elbow": [0, -.3, 1], "wrist": [0, -.6, 1]}

    def begin_four_camera_capture(self, views, cameras, camera_sites, rig, owned, output):
        self.output = Path(output)
        (self.output / "trace.jsonl").touch()

    def tick(self):
        self.frames += 1
        return self.frames

    def read_original_signal_frame(self, frame, built):
        if self.missing_arm:
            return {"operator_vehicle_contact_point": [1, 1],
                    "operator_heading": [1, 0]}
        return {"operator_vehicle_contact_point": [1 + min(frame / 100, 7), 1],
                "operator_heading": [1, 0],
                "right_arm": {"shoulder": [0, 0, 1], "elbow": [0, -.3, 1],
                              "wrist": [0, -.6, 1]}}

    def capture_frame_identities(self, frame):
        return {name: frame for name in VIEWS}

    def record_original_trace_frame(self, frame, time_s, built, output):
        with (self.output / "trace.jsonl").open("a") as stream:
            stream.write(json.dumps({"frame": frame, "time_s": time_s,
                                     "position_m": [frame / 100, 1, 0]}) + "\n")

    def finish_four_camera_capture(self, output):
        for name in VIEWS:
            (self.output / (name + ".mkv")).write_bytes(b"diagnostic camera placeholder")

    def camera_frame_counts(self):
        return {name: FRAMES for name in VIEWS}

    def native_source_kind(self):
        return "original_native_capture"

    def destroy(self, actor):
        self.destroyed.append(actor)


class RunnerTest(unittest.TestCase):
    def setUp(self):
        Path(".runtime-work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.case_id = ASSIGNMENT + "__bicycle_horizontal_right_arm"
        self.scene = {
            "operator_vehicle_kind": "bicycle", "operator_identity": "source rider",
            "highway_status": "highway", "roadway_status": "roadway",
            "roadway_polygon": [[-2, -12], [12, -12], [12, 12], [-2, 12]],
            "shoulder_polygon": [[-2, -15], [12, -15], [12, -12], [-2, -12]],
            "right_turn_route": [[0, 0], [9, 0], [9, -9]],
            "rider_arm_rig": {"right_shoulder": "s", "right_elbow": "e",
                              "right_wrist": "w", "independent_actuation": True,
                              "mount_offset_m": [0, 0, 0.6],
                              "posture_rotations_deg": {name: {bone: [0, 0, 0] for bone in
                                  ("s", "e", "w")} for name in
                                  ("horizontal_right_arm", "downward_right_arm", "bent_right_arm")}},
            "camera_sites": {name: [0, 0, 3, 0, 0, 0] for name in VIEWS},
            "cycle_blueprint_id": "cycle", "rider_blueprint_id": "rider"}
        for name in SOURCES:
            self.scene[name + "_source_sha256"] = hashlib.sha256(
                b"road" if name == "map_opendrive" else name.encode()).hexdigest()
        self.config = json.loads((ROOT / "config.json").read_text())
        (self.output / "config.json").write_text(json.dumps(self.config))

    def test_full_capture_and_source_measurement(self):
        adapter = Adapter(b"road")
        result = run(adapter, self.scene, self.config, self.output, "1" * 64)
        self.assertEqual(result["frame_count"], FRAMES)
        self.assertEqual(adapter.destroyed, ["rider", "cycle"])
        measured = measure(case_id=self.case_id,
                           context_path=self.output / "signal-context.json",
                           trace_path=self.output / "signal-readback.jsonl",
                           receipt_path=self.output / "signal-receipt.json")
        self.assertEqual(len(measured["roadway_frames"]), FRAMES)
        self.assertEqual(measured["signal_form_judgment"], "unresolved")
        report = analyze(self.output, self.output / "analysis-report.json")
        self.assertEqual(report["case_id"], self.case_id)
        self.assertTrue((self.output / "result.json").is_file())
        self.assertEqual(len(list((self.output / "channels").glob("*.jsonl"))), 4)
        self.assertTrue((self.output / "channels/reviewed_signal_scene.json").is_file())

    def test_missing_actual_arm_readback_fails_and_cleans(self):
        adapter = Adapter(b"road")
        adapter.missing_arm = True
        with self.assertRaisesRegex(ValueError, "arm and roadway readback missing"):
            run(adapter, self.scene, self.config, self.output, "1" * 64)
        self.assertEqual(adapter.destroyed, ["rider", "cycle"])


if __name__ == "__main__":
    unittest.main()
