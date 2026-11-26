"""Saved-only analysis of a clearly synthetic original-frame fixture."""
import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import build
from native_capture import capture
from test_native_capture import Adapter, CaptureTest


class AnalysisTest(CaptureTest):
    def setUp(self):
        super().setUp()
        package = Path(__file__).resolve().parents[1]
        suffix = 'stopped_leftmost_clear'
        case = package.name + '__' + suffix
        self.attempt = self.root / 'attempt'
        self.attempt.mkdir()
        for name in ('config.json', 'construction.json'):
            shutil.copy2(package / 'cases' / suffix / name, self.attempt / name)
        shutil.copy2(package / 'case-plan.json', self.attempt / 'case-plan.json')
        self.config = json.loads((self.attempt / 'config.json').read_text())
        self.assertEqual(self.config['selected_case_id'], case)
        self.packet['spawn_plan'] = {
            'ego': {'lane_id': 'left', 'location_xyz_m': [0, 3.5, 0],
                    'rotation_rpy_deg': [0, 0, 0], 'blueprint_id': 'vehicle.test',
                    'source_citation': 'fixture-map'},
            'pedestrians': [], 'other_traffic': []}
        self.write_packet()
        capture(Adapter(), self.config, self.packet_path, self.attempt / 'original-attempt')
        original = self.attempt / 'original-attempt'
        rows = [json.loads(line) for line in (original / 'history.jsonl').read_text().splitlines()]
        trace = [{'frame': row['native_frame']['frame'],
                  'time_s': row['native_frame']['time_s']}
                 for row in rows]
        video = [{'video_frame': index, 'carla_frame': row['native_frame']['frame'],
                  'time_s': row['native_frame']['time_s']}
                 for index, row in enumerate(rows)]
        (self.attempt / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
        (self.attempt / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in video))

    def test_source_sealed_saved_analysis(self):
        report, result = build(self.attempt)
        self.assertTrue(report['analysis_complete'])
        self.assertEqual(result['provenance_kind'], 'synthetic_fixture')
        self.assertFalse(result['physical_acceptance_claimed'])
        self.assertEqual(len(result['recording_evidence']), 9)
        self.assertIn('stop_reference_front_signed_distance',
                      {item['name'] for item in result['recording_evidence']})
        self.assertIn('directed_conflict_release_delay',
                      {item['name'] for item in result['recording_evidence']})
        self.assertEqual(len(list((self.attempt / 'channels').glob('*.jsonl'))), 8)

    def test_reject_tampered_original_history(self):
        original = self.attempt / 'original-attempt' / 'history.jsonl'
        original.write_text(original.read_text() + '{}\n')
        with self.assertRaisesRegex(ValueError, 'sealed original'):
            build(self.attempt)

    def test_reject_tampered_original_camera(self):
        archive = self.attempt / 'original-attempt' / 'overview.zip'
        archive.write_bytes(archive.read_bytes() + b'tamper')
        with self.assertRaisesRegex(ValueError, 'sealed original camera'):
            build(self.attempt)

    def test_reject_wrong_frame_join(self):
        path = self.attempt / 'video_frames.jsonl'
        rows = path.read_text().splitlines()
        first = json.loads(rows[0])
        first['carla_frame'] = -1
        rows[0] = json.dumps(first)
        path.write_text('\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'timestamp/frame join'):
            build(self.attempt)


if __name__ == '__main__':
    unittest.main()
