import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_count_capture import CountCapture


def _construction():
    return {"case_id": "case__animal_above", "kind": "additional_animal_count",
            "expected_count": 2, "actors": [object(), object()],
            "declared_blueprint_ids": ["animal.source", "animal.source"],
            "packet_sha256": hashlib.sha256(b"packet").hexdigest(),
            "opendrive_sha256": hashlib.sha256(b"map").hexdigest()}


def _snapshot(frame):
    return SimpleNamespace(frame=frame, timestamp=SimpleNamespace(elapsed_seconds=frame / 20))


class CountCaptureTests(unittest.TestCase):
    def test_full_episode_write_once_and_source_seal(self):
        capture = CountCapture(_construction())
        actors = capture.construction["actors"]
        def read(actor):
            return {"actor_id": actors.index(actor) + 100, "type_id": "animal.source", "alive": True}
        for frame in range(900):
            capture.append(_snapshot(frame), read)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "count-source.jsonl"
            receipt = capture.close(output)
            self.assertEqual(receipt["sample_count"], 900)
            self.assertEqual(receipt["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertFalse(receipt["physical_acceptance_claimed"])
            with self.assertRaisesRegex(ValueError, "already closed"):
                capture.append(_snapshot(900), read)
            with self.assertRaisesRegex(ValueError, "requires one complete|already exists"):
                capture.close(output)

    def test_rejects_frame_gap_and_missing_readback(self):
        capture = CountCapture(_construction())
        actors = capture.construction["actors"]
        read = lambda actor: {"actor_id": actors.index(actor) + 100,
                              "type_id": "animal.source", "alive": True}
        capture.append(_snapshot(0), read)
        with self.assertRaisesRegex(ValueError, "discontinuity"):
            capture.append(_snapshot(2), read)
        with self.assertRaisesRegex(ValueError, "readback missing"):
            capture.append(_snapshot(1), lambda actor: {"actor_id": 100, "alive": True})

    def test_rejects_slow_original_tick(self):
        capture = CountCapture(_construction())
        actors = capture.construction["actors"]
        read = lambda actor: {"actor_id": actors.index(actor) + 100,
                              "type_id": "animal.source", "alive": True}
        capture.append(_snapshot(0), read)
        slow = SimpleNamespace(frame=1, timestamp=SimpleNamespace(elapsed_seconds=.1))
        with self.assertRaisesRegex(ValueError, "discontinuity"):
            capture.append(slow, read)

    def test_rejects_actor_identity_change_and_incomplete_episode(self):
        capture = CountCapture(_construction())
        actors = capture.construction["actors"]
        capture.append(_snapshot(0), lambda actor: {"actor_id": actors.index(actor) + 100,
                                                     "type_id": "animal.source", "alive": True})
        with self.assertRaisesRegex(ValueError, "identity changed"):
            capture.append(_snapshot(1), lambda actor: {"actor_id": actors.index(actor) + 200,
                                                         "type_id": "animal.source", "alive": True})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "900-frame"):
                capture.close(Path(directory) / "count-source.jsonl")

    def test_rejects_original_blueprint_mismatch(self):
        capture = CountCapture(_construction())
        actors = capture.construction["actors"]
        with self.assertRaisesRegex(ValueError, "blueprint differs"):
            capture.append(_snapshot(0), lambda actor: {"actor_id": actors.index(actor) + 100,
                                                        "type_id": "different.actor", "alive": True})


if __name__ == "__main__":
    unittest.main()
