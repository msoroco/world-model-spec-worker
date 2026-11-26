"""Source-gated 20 Hz Native interior control tests."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from interior_attention import request_control


SENSOR = {"review_status": "reviewed", "observable": "original_eyes_off_road_duration_s",
          "sensor_id": "interior-1", "source_sha256": "a" * 64}


class Adapter:
    def __init__(self):
        self.changed = False

    def set_interior_attention(self, actor, case_id, frame_index, sensor_id, requested):
        assert actor == "actor"
        return {"source_kind": "original_native_interior_control",
                "case_id": case_id, "frame_index": frame_index,
                "sensor_id": sensor_id, "sensor_source_sha256": SENSOR["source_sha256"],
                "requested_eyes_off_road": not requested if self.changed else requested,
                "native_verified": True}


class InteriorControlTests(unittest.TestCase):
    def test_exact_requested_frames_and_readback(self):
        adapter = Adapter()
        for target in (0, 5, 10):
            observed = [request_control(adapter, "actor", "attention-case", index,
                                        target, SENSOR)["requested_eyes_off_road"]
                        for index in range(900)]
            self.assertEqual(sum(observed), target * 20)

    def test_missing_source_and_changed_readback_rejected(self):
        with self.assertRaisesRegex(ValueError, "source-reviewed"):
            request_control(Adapter(), "actor", "attention-case", 0, 5,
                            dict(SENSOR, review_status="unreviewed"))
        adapter = Adapter()
        adapter.changed = True
        with self.assertRaisesRegex(ValueError, "readback differs"):
            request_control(adapter, "actor", "attention-case", 0, 5, SENSOR)

    def test_off_grid_target_rejected(self):
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            request_control(Adapter(), "actor", "attention-case", 0, 5.01, SENSOR)
