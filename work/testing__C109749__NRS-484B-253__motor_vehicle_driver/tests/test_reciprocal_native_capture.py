"""A diagnostic adapter proves three-actor Native source sealing only."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reciprocal_native_capture import capture_reciprocal
from test_native_acquisition import Adapter, NativeAcquisition, body
from saved_left_turn import ASSIGNMENT_ID


class ThreeActor(Adapter):
    def __init__(self):
        super().__init__()
        self.alias = False
        self.omit = False

    def tick(self):
        frame, time_s, primary, cameras = super().tick()
        later = {"later_opponent_actor_id": 12 if self.alias else 13,
                 "later_opponent_vertices": body(2, 0),
                 "later_opponent_heading": [-1, 0],
                 "later_opponent_speed_mps": 4,
                 "later_opponent_braking": True,
                 "later_opponent_driver_control_source": "original get_control"}
        if self.omit:
            del later["later_opponent_vertices"]
        return frame, time_s, primary, cameras, later


class ReciprocalNativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = NativeAcquisition()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def test_seals_third_actor_original_frame_source(self):
        case = ASSIGNMENT_ID + "__reciprocal_yield"
        out = self.fixture.root / "reciprocal"
        paths = capture_reciprocal(adapter=ThreeActor(), case_id=case,
                                   map_path=self.fixture.map_path, output=out,
                                   frame_count=3)
        receipt = json.loads(paths["receipt_path"].read_text())
        source = paths["later_opponent_path"]
        self.assertEqual(receipt["later_opponent_trace_sha256"],
                         hashlib.sha256(source.read_bytes()).hexdigest())
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        self.assertEqual([row["frame"] for row in rows], [100, 101, 102])
        self.assertEqual({row["later_opponent_actor_id"] for row in rows}, {13})
        self.assertTrue(receipt["diagnostic_fixture"])

    def test_rejects_aliased_and_missing_later_actor(self):
        for fault in ("alias", "omit"):
            with self.subTest(fault=fault):
                adapter = ThreeActor()
                setattr(adapter, fault, True)
                with self.assertRaisesRegex(ValueError, "three distinct|field missing"):
                    capture_reciprocal(adapter=adapter,
                                       case_id=ASSIGNMENT_ID + "__reciprocal_yield",
                                       map_path=self.fixture.map_path,
                                       output=self.fixture.root / fault,
                                       frame_count=3)
                self.assertFalse((self.fixture.root / fault / "acquisition-receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
