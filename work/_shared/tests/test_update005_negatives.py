"""Negative CPU checks for update 005's original-output boundary."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'runtime/main-pipeline-v1/scenario_pipeline'))
from batch_pipeline.carla import validate_attempt
from worker_exchange.native_output import validate_result
from worker_exchange.package_compatibility import check_receipts, CHECKS
from worker_exchange.common import digest, sha, tree, write


class NativeBoundaryNegatives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.attempt = Path(self.tmp.name)
        self.description = {'channels': [{'name': 'kin.speed', 'unit': 'm/s',
            'sampling_rate_hz': 20, 'method': 'native actor velocity',
            'time_window': 'entire original run', 'reference_frame': 'CARLA world',
            'uncertainty': 'diagnostic source'}], 'context_inputs': [], 'limitations': []}
        self.result = {'case_id': 'test', 'measured_values': {'speed': 1},
            'target_checks': [{'target': 'speed', 'requested': 1, 'measured': 1,
                               'method': 'original velocity', 'tolerance': .1,
                               'matched': True, 'physical_cause_confirmed': False,
                               'cause_evidence': 'trace.jsonl'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False, 'termination_reason': 'diagnostic subset',
            'physical_failure_flags': {'unknown': True}, 'trace_reference': 'trace.jsonl',
            'video_references': ['missing-video.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': self.description,
            'recording_evidence': [{'name': 'kin.speed', 'unit': 'm/s',
                                    'reference': 'speed.jsonl'}], 'realized_observables': {}}
        (self.attempt / 'trace.jsonl').write_text(json.dumps({'frame': 7, 'time_s': .05,
            'position': {'x': 0, 'y': 0, 'z': 0}, 'heading_deg': 0, 'speed_mps': 1}) + '\n')
        (self.attempt / 'speed.jsonl').write_text(json.dumps({'time_s': .05, 'value': 1}) + '\n')
        (self.attempt / 'video_frames.jsonl').write_text(json.dumps({'video_frame': 0,
            'native_frame': 7, 'time_s': .05}) + '\n')

    def validate(self):
        write(self.attempt / 'result.json', self.result)
        return validate_attempt(self.attempt, {'cell': {'cell_id': 'test'},
            'actor': 'motor_vehicle_driver', 'case': {'case_id': 'test'}},
            {'recording_description': self.description}, {'recorded_exit_code': 0}, {})

    def test_missing_native_result_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Missing native result field'):
            validate_result({'case_id': 'test'})

    def test_missing_original_carla_frame_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Video/trace frame mismatch'):
            self.validate()

    def test_missing_channel_rejected(self):
        self.result['recording_evidence'] = []
        with self.assertRaisesRegex(ValueError, 'Missing recording evidence: kin.speed'):
            self.validate()

    def test_incomplete_motion_remains_incomplete(self):
        self.assertFalse(validate_result(self.result)['maneuver_completed'])
        self.assertFalse(validate_result(self.result)['target_checks'][0]['physical_cause_confirmed'])


class ReceiptNegatives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.folder = self.repo / 'work/assignment'
        self.folder.mkdir(parents=True)
        self.fixture = self.repo / 'work/_shared/fixture'
        self.fixture.mkdir(parents=True)
        (self.fixture / 'trace.jsonl').write_text('source')
        files = [{'path': 'config.json', 'content': json.dumps({'required_atoms': ['env.visibility']})},
                 {'path': 'analyze.py', 'content': 'pass'},
                 {'path': 'runner.py', 'content': 'pass'}]
        write(self.folder / 'construction.json', {'files': files,
            'recording_description': {'channels': [{'name': 'env.visibility'}]}})
        (self.folder / 'analysis.log').write_text('')
        proof = {'format': 'worker-package-compatibility-v1', 'case_id': 'case',
                 'construction_sha256': sha(self.folder / 'construction.json'),
                 'runtime_manifest_sha256': 'runtime', 'fixture_sha256': digest(tree(self.fixture)),
                 'analysis_sha256': sha(self.folder / 'analysis.log'),
                 'log_sha256': sha(self.folder / 'analysis.log'),
                 'passed': True, 'checks': sorted(CHECKS)}
        # The test reaches acquisition validation only after all static hashes pass.
        import hashlib
        proof['analysis_sha256'] = hashlib.sha256(b'pass').hexdigest()
        write(self.folder / 'proof.json', proof)
        self.entry = {'case_id': 'case', 'construction': 'construction.json',
            'construction_sha256': sha(self.folder / 'construction.json'),
            'measurement_procedure': {'entrypoint': 'analyze.py'},
            'acquisition': {},
            'compatibility': {'receipt': 'proof.json', 'sha256': sha(self.folder / 'proof.json'),
                              'fixture': 'work/_shared/fixture', 'log': 'analysis.log'}}
        self.manifest = {'runtime_manifest_sha256': 'runtime', 'cases': [self.entry]}

    def test_missing_environmental_acquisition_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Mandatory observation lacks acquisition'):
            check_receipts(self.repo, self.folder, self.manifest)

    def test_changed_receipt_hash_rejected(self):
        self.entry['compatibility']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Compatibility receipt changed'):
            check_receipts(self.repo, self.folder, self.manifest)


if __name__ == '__main__':
    unittest.main()
