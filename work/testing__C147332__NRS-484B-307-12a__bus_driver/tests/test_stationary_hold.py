import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stationary_hold import SOURCES, audit


def make_attempt(root, *, second_frame=101, second_time=.05):
    bodies, traces, controls, frames = [], [], [], []
    for index, (number, time) in enumerate(((100, 0), (second_frame, second_time))):
        body = [[0, 0], [2, 0], [2, 2], [0, 2]]
        bodies.append({'frame': number, 'elapsed_seconds': time,
                       'bus_footprint': body})
        traces.append({'frame': number, 'time_s': time, 'position_m': [1, 1, 0],
                       'speed_mps': 0})
        controls.append({'frame': number, 'elapsed_seconds': time,
                         'requested_control': {'brake': 1, 'throttle': 0}})
        frames.append({'video_frame': index, 'carla_frame': number, 'time_s': time})
    hashes = {}
    for name, values in zip(SOURCES, (bodies, traces, controls, frames)):
        path = root / name
        path.write_text(''.join(json.dumps(value) + '\n' for value in values))
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root / 'acquisition.json').write_text(json.dumps(hashes) + '\n')


class StationaryHoldSequenceTests(unittest.TestCase):
    def test_complete_source_bound_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root)
            self.assertEqual(audit(root)['frames'], 2)

    def test_resealed_native_frame_gap_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root, second_frame=102)
            with self.assertRaisesRegex(ValueError, '20 Hz frame sequence has a gap'):
                audit(root)

    def test_resealed_timestamp_gap_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_attempt(root, second_time=.15)
            with self.assertRaisesRegex(ValueError, '20 Hz frame sequence has a gap'):
                audit(root)


if __name__ == '__main__':
    unittest.main()
