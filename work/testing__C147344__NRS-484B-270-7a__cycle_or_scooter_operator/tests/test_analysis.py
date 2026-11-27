"""Recorded-only original source checks; synthetic video is never accepted."""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import analyze
from interference import CASES
from runner import ASSIGNMENT, VIEWS
from test_interference import rows_for, scene_for


def write_test_attempt(root, case):
    config = json.loads((Path(__file__).resolve().parents[1] /
                         'config.json').read_text())
    config['selected_case_id'] = ASSIGNMENT + '__' + case.suffix
    (root / 'config.json').write_text(json.dumps(config) + '\n')
    scene = scene_for(case)
    scene['reviewed_scene_packet_sha256'] = 'd' * 64
    scene['electric_bicycle_classification'] = scene['electric_bicycle']
    scene['distinct_motor_vehicle_identity'] = (
        scene['motor_vehicle']['vehicle_id'])
    scene['authored_plan_interval'] = (
        scene['intention_declaration'] or {'status': 'undeclared'})
    (root / 'scene-context.json').write_text(json.dumps(scene) + '\n')
    (root / 'interaction-readback.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in rows_for(scene, case)))
    (root / 'trace.jsonl').write_text('{}\n')
    (root / 'video_frames.jsonl').write_text('{}\n')
    for view in VIEWS:
        (root / (view + '.mkv')).write_bytes(b'fixture-only-not-video')
    names = ('config.json', 'scene-context.json',
             'interaction-readback.jsonl', 'trace.jsonl',
             'video_frames.jsonl') + tuple(view + '.mkv' for view in VIEWS)
    files = {name: {'sha256': hashlib.sha256(
        (root / name).read_bytes()).hexdigest()} for name in names}
    (root / 'original-sources.json').write_text(json.dumps({
        'source_kind': 'original_native_capture',
        'accepted_original_source': True,
        'case_id': config['selected_case_id'],
        'reviewed_scene_packet_sha256': 'd' * 64,
        'frame_count': 600,
        'camera_frame_counts': {view: 600 for view in VIEWS},
        'files': files}) + '\n')


class AnalysisTest(unittest.TestCase):
    def test_analysis_reads_exact_original_sources(self):
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            write_test_attempt(root, CASES[0])
            report, native = analyze(root)
            self.assertEqual(report['case_id'], ASSIGNMENT + '__' + CASES[0].suffix)
            self.assertFalse(report['physical_acceptance_claimed'])
            self.assertIsNone(report['legal_judgment'])
            self.assertFalse(native['maneuver_completed'])

    def test_changed_original_motion_rejected(self):
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            write_test_attempt(root, CASES[0])
            (root / 'interaction-readback.jsonl').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
