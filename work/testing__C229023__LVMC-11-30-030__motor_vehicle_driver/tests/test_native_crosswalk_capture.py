"""CPU checks for original Native tick joins; no CARLA connection is made."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from crosswalk_measurements import ASSIGNMENT_ID, measure
from native_crosswalk_capture import CAMERAS, FRAME_COUNT, NativeCrosswalkRecorder


CASE = ASSIGNMENT_ID + "__unmarked_pass"
ACTORS = {"ego": "ego-17", "lead": "lead-18", "pedestrian": "walker-19"}


def vertices(x):
    return [[x + dx, y, z] for dx in (-1.0, 1.0) for y in (-0.5, 0.5) for z in (0.0, 1.0)]


def observations(frame, x):
    return {"ego": {"actor_id": ACTORS["ego"], "center": [x, 0.0],
                    "vertices": vertices(x), "speed_mps": 3.0,
                    "source_ref": f"native/ego/{frame}"},
            "lead": {"actor_id": ACTORS["lead"], "center": [5.0, 0.0],
                     "vertices": vertices(5.0), "speed_mps": 0.0,
                     "source_ref": f"native/lead/{frame}"},
            "pedestrian": {"actor_id": ACTORS["pedestrian"], "center": [7.0, 0.0],
                           "source_ref": f"native/walker/{frame}"}}


def context():
    return {"case_id": CASE, "map_sha256": "a" * 64, "layout": "intersection",
            "junction_kind": "road_intersection",
            "crosswalk": {"kind": "unmarked", "polygon": [[6.0, -2.0], [8.0, -2.0],
                                                            [8.0, 2.0], [6.0, 2.0]],
                          "opposite_sidewalk_lateral_lines": "original/sidewalk",
                          "curb_or_traveled_edge_sources": "original/curb"},
            "stopped_vehicle_purpose": {"claim": "permit_pedestrian",
                                        "source_ref": "original/independent-observer"},
            "ego_vehicle_identity": ACTORS["ego"],
            "lead_vehicle_identity": ACTORS["lead"],
            "pedestrian_identity": ACTORS["pedestrian"],
            "road_axis": {"origin": [0.0, 0.0], "forward": [1.0, 0.0]}}


class NativeCrosswalkCaptureTests(unittest.TestCase):
    def setUp(self):
        self.recorder = NativeCrosswalkRecorder(case_id=CASE, context=context(), actor_ids=ACTORS)

    def append(self, frame=20, x=0.0):
        return self.recorder.append(world_frame=frame, actors=observations(frame, x),
                                    camera_frames={name: SimpleNamespace(frame=frame) for name in CAMERAS})

    def test_identity_and_same_tick_checks(self):
        bad = observations(20, 0.0)
        bad["ego"]["actor_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "actor identity"):
            self.recorder.append(world_frame=20, actors=bad,
                                 camera_frames={name: SimpleNamespace(frame=20) for name in CAMERAS})
        with self.assertRaisesRegex(ValueError, "camera image frame"):
            self.recorder.append(world_frame=20, actors=observations(20, 0.0),
                                 camera_frames={name: SimpleNamespace(frame=21) for name in CAMERAS})
        self.append()
        with self.assertRaisesRegex(ValueError, "consecutive"):
            self.append(frame=22)

    def test_rejects_nonphysical_observation_values(self):
        for key, value in (("speed_mps", True), ("speed_mps", float("nan")),
                           ("vertices", [[0.0, 0.0, 0.0]]), ("center", [False, 0.0])):
            bad = observations(20, 0.0)
            bad["ego"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.recorder.append(world_frame=20, actors=bad,
                                     camera_frames={name: SimpleNamespace(frame=20) for name in CAMERAS})
        with self.assertRaisesRegex(ValueError, "complete"):
            with tempfile.TemporaryDirectory(dir=".runtime-work") as directory:
                self.recorder.write(directory)

    def test_complete_capture_replays_saved_measurement(self):
        for index in range(FRAME_COUNT):
            frame = 100 + index
            self.append(frame, -5.0 + index * .03)
        with tempfile.TemporaryDirectory(dir=".runtime-work") as directory:
            receipt = self.recorder.write(directory)
            root = Path(directory)
            self.assertEqual(receipt["trace_sha256"], hashlib.sha256((root / "trace.jsonl").read_bytes()).hexdigest())
            self.assertEqual(receipt["frame_map_sha256"], hashlib.sha256((root / "frame-map.jsonl").read_bytes()).hexdigest())
            result = measure(case_id=CASE, context_path=root / "context.json",
                             trace_path=root / "trace.jsonl", receipt_path=root / "receipt.json")
            self.assertEqual(result["frame_count"], FRAME_COUNT)
            self.assertTrue(result["rear_approach_frames"])
            self.assertTrue(result["ego_ahead_frames"])
            self.assertEqual(result["physical_acceptance"], "unverified")
            with self.assertRaisesRegex(ValueError, "fresh"):
                self.recorder.write(directory)


if __name__ == "__main__":
    unittest.main()
