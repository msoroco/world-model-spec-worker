import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import officer_reference_saved_finalizer as finalizer
from stopping_reference import from_authored_site


class OfficerReferenceSavedFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name)
        (self.attempt / 'capture').mkdir()
        self.site = ROOT / 'line-reference-site.xodr'
        case_id = ('testing__C158196__NRS-484B-257-2__motor_vehicle_driver__'
                   'stop_line_reference')
        (self.attempt / 'config.json').write_text(json.dumps({
            'selected_case_id': case_id, 'law_id': 'NRS-484B-257-2',
            'cell_id': 'C158196', 'actor': 'motor_vehicle_driver'}))
        reference = from_authored_site(self.site)
        x = reference['x_m'] - 2
        body = [[x + dx, dy] for dx, dy in
                ((-1, -1), (-1, 1), (1, -1), (1, 1),
                 (-1, -1), (-1, 1), (1, -1), (1, 1))]
        capture = {'format': 'worker-subsection-2-officer-native-capture',
                   'case_id': case_id, 'site_sha256':
                   hashlib.sha256(self.site.read_bytes()).hexdigest(),
                   'fixed_delta_seconds': 0.05, 'frame_count': 600, 'rows': []}
        frames, trace, evidence = [], [], []
        for i in range(600):
            fid, time_s = 101 + i, (i + 1) * 0.05
            cameras = {name: {'carla_frame': fid, 'video_frame': i,
                              'raw_source': str(self.attempt / (name + '.mkv')) +
                              '#frame-' + str(i)} for name in finalizer.CAMERAS}
            capture['rows'].append({'frame_index': i, 'carla_frame': fid,
                                    'time_s': time_s, 'stopping_reference': reference,
                                    'ego_body_vertices_xy_m': body,
                                    'ego_front_x_m': x + 1, 'ego_speed_mps': 0.0,
                                    'camera_raw_sources': cameras})
            frames.append({'video_frame': i, 'carla_frame': fid, 'time_s': time_s})
            trace.append({'frame': fid, 'time_s': time_s})
            evidence.append({'original_frame': fid})
        (self.attempt / 'officer-reference-capture.json').write_text(json.dumps(capture))
        for name, rows in (('video_frames.jsonl', frames), ('trace.jsonl', trace),
                           ('capture/evidence.jsonl', evidence)):
            (self.attempt / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
        for name in finalizer.CAMERAS:
            (self.attempt / (name + '.mkv')).write_text('test camera placeholder')

    @patch.object(finalizer, '_probe')
    def test_reference_sources_are_joined_and_judgment_remains_open(self, probe):
        result = finalizer.analyze(self.attempt, self.site)
        self.assertEqual(result['reference_measurement']['original_frame_count'], 600)
        self.assertEqual(result['legal_exception_judgment'], 'unresolved')
        self.assertFalse(result['physical_cause_confirmed'])
        self.assertEqual(probe.call_count, 4)

    @patch.object(finalizer, '_probe')
    def test_changed_original_frame_is_rejected(self, probe):
        path = self.attempt / 'video_frames.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[23]['carla_frame'] += 1
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'frame differs'):
            finalizer.analyze(self.attempt, self.site)
        probe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
