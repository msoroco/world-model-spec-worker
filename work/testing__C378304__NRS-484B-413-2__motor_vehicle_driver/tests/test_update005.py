"""CPU-only sensor and native writer doubles; no simulator allocation."""
import json
import queue
import tempfile
import unittest
from pathlib import Path
from runner import append_frame_map, image_for_frame
from worker_exchange.native_output import FrameMap


class SensorFrame:
    def __init__(self, frame):
        self.frame = frame
        self.width = 2
        self.height = 2
        self.raw_data = b'\x00' * 16


class CaptureWriterTests(unittest.TestCase):
    def test_sensor_frame_is_written_once_with_carla_identity(self):
        messages = queue.Queue()
        messages.put(SensorFrame(17))
        messages.put(SensorFrame(18))
        image = image_for_frame(messages, 18)
        self.assertEqual(image.frame, 18)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'video_frames.jsonl'
            with FrameMap(path) as mapping:
                append_frame_map(mapping, image.frame, 0.05,
                                 {'view0': {'native_frame': image.frame,
                                            'width': image.width, 'height': image.height}})
                with self.assertRaisesRegex(ValueError, 'increase'):
                    append_frame_map(mapping, image.frame, 0.1, {})
            rows = [json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['carla_frame'], 18)
            self.assertEqual(rows[0]['native_frame'], 18)
            self.assertEqual(rows[0]['video_frame'], 0)


if __name__ == '__main__':
    unittest.main()
