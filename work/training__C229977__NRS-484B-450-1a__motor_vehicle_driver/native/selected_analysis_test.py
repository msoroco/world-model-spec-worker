"""Synthetic shape tests; no physical or statutory observation claim."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from finalize_sidewalk import observe, required


class SavedShape(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.path = Path(self.temp.name)
        self.write(True)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, on_sidewalk):
        location = -5.0 if on_sidewalk else -1.75
        body = [[19, location - .5], [21, location - .5],
                [21, location + .5], [19, location + .5]]
        trace, mapping, cameras = [], [], []
        for i in range(600):
            native = i + 100
            time = i / 20
            trace.append({'frame': i, 'native_frame': native, 'time_s': time,
                          'actor_id': 7, 'speed_mps': 0.0,
                          'vehicle_footprint_m': body})
            mapping.append({'video_frame': i, 'native_frame': native,
                            'time_s': time, 'camera_native_frames': {
                                name: native for name in ('overview', 'approach',
                                'reference_corner', 'driver_reference')}})
            cameras.extend({'frame': i, 'native_frame': native, 'camera': name}
                           for name in ('overview', 'approach',
                                        'reference_corner', 'driver_reference'))
        for name, values in [('vehicle-trace.jsonl', trace),
                             ('video_frames.jsonl', mapping),
                             ('camera-frames.jsonl', cameras)]:
            (self.path / name).write_text(''.join(json.dumps(v) + '\n' for v in values))
        (self.path / 'map-packet.json').write_text(json.dumps({
            'map_acquisition': 'synthetic_shape_test',
            'sidewalk_polygon_m': [[0, -7], [100, -7],
                                   [100, -3.5], [0, -3.5]]}) + '\n')
        (self.path / 'authority-context.json').write_text('{}\n')
        (self.path / 'native-road.xodr').write_text('<OpenDRIVE/>\n')

    def test_on_sidewalk(self):
        measured = observe(self.path)
        self.assertEqual(measured['rest_and_overlap_frames'], 600)
        self.assertFalse(measured['map_legal_context_complete'])

    def test_off_sidewalk(self):
        self.write(False)
        self.assertEqual(observe(self.path)['rest_and_overlap_frames'], 0)

    def test_missing_required_map(self):
        (self.path / 'map-packet.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source: map-packet.json'):
            observe(self.path)

    def test_camera_join_rejected(self):
        source = self.path / 'camera-frames.jsonl'
        data = source.read_text().splitlines()
        data.pop()
        source.write_text('\n'.join(data) + '\n')
        with self.assertRaisesRegex(ValueError, 'Incomplete original sidewalk'):
            observe(self.path)


if __name__ == '__main__':
    unittest.main()
