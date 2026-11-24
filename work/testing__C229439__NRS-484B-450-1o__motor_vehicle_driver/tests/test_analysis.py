import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
from analysis import analyze


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        scratch = FOLDER.parents[1] / '.runtime-work/c229439-analysis-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)
        polygon = [[0, 0], [4, 0], [4, 4], [0, 4]]
        self.site = {'cell_id': 'C229439', 'parking_polygon': polygon}
        self.device = {'device_id': 'sign', 'exact_instruction': 'NO PARKING',
                       'governed_polygon': polygon, 'authority_source': 'review',
                       'placement_source': 'review', 'traffic_purpose_source': 'review',
                       'legal_consistency_source': 'review'}
        self.rows = [{'frame': i, 'time_s': i * .05, 'case_id': 'case',
                      'subject_id': 'ego', 'device_id': 'sign',
                      'device_instruction': 'NO PARKING', 'device_effective': True,
                      'prohibited_actions': ['park'], 'halt_activity': 'park',
                      'traffic_conflict': False, 'police_direction': False,
                      'law_direction': False, 'device_direction': False,
                      'speed_mps': 0.0,
                      'body_corners_xy': [[1, 1], [2, 1], [2, 2], [1, 2]]}
                     for i in range(5)]
        refs = {}
        for name, value in (('site-source.json', self.site),
                            ('device-source.json', self.device),
                            ('actor_rows.json', self.rows)):
            path = self.root / name
            path.write_text(json.dumps(value) + '\n')
            refs[name] = {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        self.attempt = {'source_context': refs, 'frame_count': 5, 'first_frame': 0,
                        'case_id': 'case', 'subject_id': 'ego', 'device_id': 'sign',
                        'device_instruction': 'NO PARKING', 'parking_polygon': polygon,
                        'halt_action': 'park'}
        (self.root / 'attempt.json').write_text(json.dumps(self.attempt) + '\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_source_measurement(self):
        report = analyze(self.root, self.root / 'report.json')
        value = report['measurements']['official_prohibition_history']['value']
        self.assertEqual(value['halt_inside_frames'], 5)
        self.assertIsNone(report['legal_judgment'])

    def test_missing_device_packet_rejected(self):
        (self.root / 'device-source.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source: device-source.json'):
            analyze(self.root, self.root / 'report.json')
        self.assertFalse((self.root / 'report.json').exists())


if __name__ == '__main__':
    unittest.main()
