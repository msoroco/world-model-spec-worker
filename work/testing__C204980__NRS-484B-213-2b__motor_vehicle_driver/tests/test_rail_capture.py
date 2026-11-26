import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rail_capture import capture
from rail_left import CASES
from test_rail_left import rows
from test_reviewed_rail import AID, make


class FakeAdapter:
    def __init__(self, map_text, case, *, missing_camera=False, wrong_frame=False):
        self.map_text = map_text
        self.case = case
        self.missing_camera = missing_camera
        self.wrong_frame = wrong_frame
        self.events = []
        self.row_index = 0

    def live_opendrive(self):
        self.events.append('map_read')
        return self.map_text

    def begin(self, scene, case_id):
        self.events.append('begin')
        self.scene = scene

    def spawn_vehicle(self, position, role):
        self.events.append('spawn')
        return 'ego'

    def set_rail_route(self, ego, route, station, left_side):
        self.events.append('route')

    def tick(self):
        return 900 + self.row_index

    def sample_original(self, frame, scene):
        row = rows(scene, self.case)[self.row_index]
        self.row_index += 1
        if self.wrong_frame:
            row['original_frame'] = frame + 1
        return row

    def camera_frames(self, frame):
        cameras = ('overview', 'approach', 'reference_corner', 'driver_reference')
        return {camera: frame for camera in cameras if not self.missing_camera or camera != 'approach'}

    def write_camera_video(self, camera, path):
        path.write_bytes(b'fixture-video-' + camera.encode())

    def close(self, owned):
        self.events.append('close')


class RailCaptureTests(unittest.TestCase):
    def test_source_gate_precedes_world_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packet, map_text, case_id = make(root)
            adapter = FakeAdapter('<wrong-map/>', CASES[2])
            output = root / 'original'; output.mkdir()
            with self.assertRaisesRegex(ValueError, 'live map hash mismatch'):
                capture(adapter, packet, root, output, case_id)
            self.assertNotIn('begin', adapter.events)
            self.assertNotIn('spawn', adapter.events)
            self.assertEqual(adapter.events[-1], 'close')

    def test_original_900_frame_source_and_camera_join(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packet, map_text, case_id = make(root)
            adapter = FakeAdapter(map_text, CASES[2])
            output = root / 'original'; output.mkdir()
            receipt = capture(adapter, packet, root, output, case_id)
            self.assertEqual(receipt['frame_count'], 900)
            self.assertFalse(receipt['physical_acceptance_claimed'])
            self.assertEqual(len((output / 'rail-frames.jsonl').read_text().splitlines()), 900)
            self.assertEqual(len(json.loads((output / 'source-hashes.json').read_text())), 11)
            self.assertEqual(adapter.events[:3], ['map_read', 'begin', 'spawn'])
            self.assertEqual(adapter.events[-1], 'close')

    def test_missing_camera_and_wrong_frame_rejected_with_cleanup(self):
        for options, error in (({'missing_camera': True}, 'camera frame join'),
                               ({'wrong_frame': True}, 'source row/frame')):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                packet, map_text, case_id = make(root)
                adapter = FakeAdapter(map_text, CASES[2], **options)
                output = root / 'original'; output.mkdir()
                with self.assertRaisesRegex(ValueError, error):
                    capture(adapter, packet, root, output, case_id)
                self.assertEqual(adapter.events[-1], 'close')


if __name__ == '__main__':
    unittest.main()
