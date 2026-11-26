"""Saved finalizer CPU fixture; synthetic source is never physical evidence."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from finalize import finalize
from measure import SOURCES, sha
from test_measure import sample


class FinalizerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve())
        self.attempt = Path(self.temp.name) / 'attempt'
        sample(self.attempt)
        assignment = 'training__C276263__NRS-484B-533__motor_vehicle_driver'
        case = assignment + '__reference'
        channels = [{'name': name, 'unit': unit, 'method': 'source-bound test',
                     'sampling_rate_hz': 20, 'time_window': '600 frames',
                     'reference_frame': 'original actor', 'uncertainty': 'physical review'}
                    for name, unit in (('engine_running', 'categorical'),
                                       ('parking_brake_set', 'categorical'),
                                       ('front_wheel_heading_to_curb_deg', 'deg'),
                                       ('unattended_interval', 'categorical'))]
        description = {'channels': channels, 'context_inputs': [], 'limitations': []}
        self.write('config.json', {'assignment_id': assignment, 'case_id': case,
                                   'recording_description': description})
        self.write('construction.json', {'case_id': case,
                                         'recording_description': description})
        self.write('acquisition-provenance.json', {'diagnostic_fixture': True})
        self.write('acquisition-hashes.json', {name: sha(self.attempt / name)
                                          for name in SOURCES})
        for name in ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                     'driver_reference.mkv'):
            (self.attempt / name).write_text('synthetic-video-placeholder')
        self.output = self.attempt / 'analysis-report.json'

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        (self.attempt / name).write_text(json.dumps(value) + '\n')

    def test_saved_positive_and_acquisition_unchanged(self):
        before = {name: sha(self.attempt / name) for name in SOURCES}
        report = finalize(self.attempt, self.output)
        self.assertTrue(report['source_complete'])
        self.assertTrue(report['diagnostic_fixture'])
        self.assertEqual(before, {name: sha(self.attempt / name) for name in SOURCES})
        result = json.loads((self.attempt / 'result.json').read_text())
        self.assertFalse(result['setup_confirmed'])
        self.assertEqual(len(result['recording_evidence']), 4)
        self.assertEqual(set(report['measurements']),
                         {'text_0_three_duties', 'reviewed_scope_0_three_duties'})
        self.assertEqual(len((self.attempt / 'channels/engine_running.jsonl').read_text().splitlines()), 600)

    def test_missing_original_source_rejected(self):
        (self.attempt / 'instrument-frames.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source'):
            finalize(self.attempt, self.output)

    def test_stale_hash_rejected(self):
        self.write('acquisition-hashes.json', {name: '0' * 64 for name in SOURCES})
        with self.assertRaisesRegex(ValueError, 'hash inventory differs'):
            finalize(self.attempt, self.output)


if __name__ == '__main__':
    unittest.main()
