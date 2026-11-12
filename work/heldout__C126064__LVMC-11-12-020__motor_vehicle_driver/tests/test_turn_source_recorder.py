import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('turn_source_recorder', HERE / 'turn_source_recorder.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Image:
    def __init__(self, frame, width=4, height=2):
        self.frame = frame
        self.timestamp = frame / 20
        self.width = width
        self.height = height
        self.raw_data = bytes([frame % 256, 4, 8, 255]) * (width * height)


class SourceRecorderTests(unittest.TestCase):
    def scene(self, temp, recorder):
        source = Path(temp) / 'source.json'
        source.write_text(json.dumps({
            'municipal_jurisdiction_source': 'CPU fixture only',
            'intersection_source': 'CPU fixture polygon',
            'authorization_source': 'CPU fixture claim, not municipal proof',
            'median_opening_with_intersecting_road': True,
            'intersection_polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]],
            'indicated_course_xy_m': [[-2, 5], [3, 5], [7, 7], [12, 7]]}))
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        recorder.record_scene('marked-turn-case', source, digest,
                              {'physical_marker_xy_m': [[1, 2]]}, 7)

    def test_four_original_streams_and_body_join(self):
        sizes = {name: (4, 2) for name in
                 ('overview', 'approach', 'reference_corner', 'driver_reference')}
        with tempfile.TemporaryDirectory() as temp:
            recorder = module.SourceRecorder(temp, sizes)
            self.scene(temp, recorder)
            for frame in (101, 102):
                for name in sizes:
                    recorder.on_frame(name, Image(frame))
                recorder.record_sample({'frame': frame, 'time_s': frame / 20,
                                        'actor_id': 7, 'corners_xy_m': [[3, 5]] * 4})
            result = recorder.seal()
            self.assertEqual(result['frames'], 2)
            self.assertEqual(result['authority_source'], 'authority_source_original.json')
            self.assertEqual(result['authority_source_sha256'], hashlib.sha256(
                (Path(temp) / result['authority_source']).read_bytes()).hexdigest())
            self.assertTrue((Path(temp) / 'turn_body.jsonl').is_file())
            self.assertTrue((Path(temp) / 'video_frames.jsonl').is_file())
            measurement_spec = importlib.util.spec_from_file_location(
                'marked_course_measurement', HERE / 'marked_course_measurement.py')
            measurement = importlib.util.module_from_spec(measurement_spec)
            measurement_spec.loader.exec_module(measurement)
            observed = measurement.measure(temp, 'marked-turn-case')
            self.assertEqual(observed['frame_count'], 2)
            self.assertIsNone(observed['direction_disobedience_legal_judgment'])
            for name in sizes:
                probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                        '-select_streams', 'v:0',
                                        '-show_entries', 'stream=nb_read_frames',
                                        '-of', 'default=nokey=1:noprint_wrappers=1',
                                        str(Path(temp) / f'{name}.mkv')],
                                       capture_output=True, text=True, check=True)
                self.assertEqual(probe.stdout.strip(), '2')

    def test_missing_camera_frame_rejected(self):
        sizes = {name: (4, 2) for name in
                 ('overview', 'approach', 'reference_corner', 'driver_reference')}
        with tempfile.TemporaryDirectory() as temp:
            recorder = module.SourceRecorder(temp, sizes)
            self.scene(temp, recorder)
            for name in list(sizes)[:-1]:
                recorder.on_frame(name, Image(101))
            recorder.record_sample({'frame': 101, 'time_s': 5.05,
                                    'actor_id': 7, 'corners_xy_m': [[0, 0]] * 4})
            with self.assertRaisesRegex(ValueError, 'do not join'):
                recorder.seal()

    def test_incomplete_original_pixel_packet_rejected(self):
        sizes = {name: (4, 2) for name in
                 ('overview', 'approach', 'reference_corner', 'driver_reference')}
        with tempfile.TemporaryDirectory() as temp:
            recorder = module.SourceRecorder(temp, sizes)
            image = Image(101)
            image.raw_data = image.raw_data[:-1]
            with self.assertRaisesRegex(ValueError, 'Incomplete original BGRA'):
                recorder.on_frame('overview', image)
            recorder.close()

    def test_scene_source_hash_and_citation_required(self):
        sizes = {name: (4, 2) for name in
                 ('overview', 'approach', 'reference_corner', 'driver_reference')}
        with tempfile.TemporaryDirectory() as temp:
            recorder = module.SourceRecorder(temp, sizes)
            source = Path(temp) / 'unreviewed.json'
            source.write_text(json.dumps({'authorization_source': 'fixture only'}))
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                recorder.record_scene('marked-turn-case', source, '0' * 64,
                                      {'physical_marker_xy_m': [[1, 2]]}, 7)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'citation missing'):
                recorder.record_scene('marked-turn-case', source, digest,
                                      {'physical_marker_xy_m': [[1, 2]]}, 7)
            recorder.close()


if __name__ == '__main__':
    unittest.main()
