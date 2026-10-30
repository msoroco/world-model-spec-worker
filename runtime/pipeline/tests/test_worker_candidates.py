"""CPU-only exact-case candidate selection and tamper checks."""
import json
import tempfile
import unittest
from pathlib import Path

from scenario_pipeline.worker_exchange.candidate_constructions import validate
from scenario_pipeline.worker_exchange.common import read, sha, write
from scenario_pipeline.worker_exchange.runtime_cli import materialize
from scenario_pipeline.worker_exchange.saved_processing import run as process_saved


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = 'testing__C1__NRS-484B-127-1__motor_vehicle_driver__base'
        self.base = self.construction('subject_127_1', 0.3)
        self.alt = self.construction('subject_127_1', 0.4)
        write(self.root/'base.json', self.base)
        write(self.root/'fallback.json', self.alt)
        self.entry = {'case_id': self.case, 'construction': 'base.json',
                      'construction_sha256': sha(self.root/'base.json'),
                      'candidate_risk': {'status': 'physical', 'reason': 'Native steering may not complete'},
                      'candidates': [{'id': 'fallback1', 'construction': 'fallback.json',
                                      'construction_sha256': sha(self.root/'fallback.json'),
                                      'trigger': {'source': 'original lane history', 'metric': 'destination_lane_reached',
                                                  'failure_condition': 'false at final observation'},
                                      'changed_knobs': ['steering_gain 0.3 to 0.4']}]}
        write(self.root/'execution-manifest.json', {'cases': [self.entry]})

    def construction(self, role, gain):
        cfg = {'cell_id': 'C1', 'law_id': 'NRS-484B-127-1', 'actor': 'motor_vehicle_driver',
               'selected_case_id': self.case, 'required_atoms': ['kin.speed'], 'source_packets': [],
               'rate_hz': 20, 'duration_s': 45, 'cameras': [{'name': 'overview'}],
               'case': {'case_id': self.case}, 'steering_gain': gain}
        return {'case_id': self.case, 'cell_id': 'C1', 'actor': 'motor_vehicle_driver',
                'recording_description': {'channels': [{'name': 'kin.speed'}]},
                'entrypoint': 'runner.py', 'files': [
                    {'path': 'config.json', 'content': json.dumps(cfg)},
                    {'path': 'runner.py', 'content': "bp.set_attribute('role_name', %r)\n" % role},
                    {'path': 'tests/test_case.py', 'content': 'import unittest\n'}]}

    def test_selects_exact_fallback_and_records_identity(self):
        validate(self.root, self.entry, 'NRS-484B-127-1', 'C1')
        target = self.root/'attempt'
        materialize(self.root/'execution-manifest.json', self.case, target, 'fallback1')
        self.assertEqual(read(target/'construction.json'), self.alt)
        self.assertEqual(read(target/'candidate-selection.json')['candidate_id'], 'fallback1')
        self.assertEqual(read(target/'candidate-selection.json')['construction_sha256'], sha(self.root/'fallback.json'))

    def test_rejects_unknown_and_tampered_candidate(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            materialize(self.root/'execution-manifest.json', self.case, self.root/'missing', 'fallback2')
        self.alt['files'][1]['content'] = "bp.set_attribute('role_name', 'subject_600_1e')\n"
        write(self.root/'fallback.json', self.alt)
        with self.assertRaisesRegex(ValueError, 'changed'):
            validate(self.root, self.entry, 'NRS-484B-127-1', 'C1')

    def test_rejects_changed_case_contract(self):
        cfg = json.loads(self.alt['files'][0]['content'])
        cfg['duration_s'] = 50
        self.alt['files'][0]['content'] = json.dumps(cfg)
        write(self.root/'fallback.json', self.alt)
        self.entry['candidates'][0]['construction_sha256'] = sha(self.root/'fallback.json')
        with self.assertRaisesRegex(ValueError, 'shared capture contract'):
            validate(self.root, self.entry, 'NRS-484B-127-1', 'C1')

    def test_delivery_gate_rejects_empty_candidate_list(self):
        self.entry['candidate_risk'] = {'status':'none', 'reason':'unverified assumption'}
        self.entry['candidates'] = []
        with self.assertRaisesRegex(ValueError, 'tested physical fallback'):
            validate(self.root, self.entry, 'NRS-484B-127-1', 'C1',
                     required=True, require_alternate=True)

    def test_strict_gate_requires_bound_positive_and_negative_proofs(self):
        with self.assertRaisesRegex(ValueError, 'offline proof'):
            validate(self.root, self.entry, 'NRS-484B-127-1', 'C1', required=True)
        (self.root/'offline.log').write_text('offline passed\n')
        self.entry['candidates'][0]['offline'] = {
            'command': 'runtime.py offline --candidate fallback1', 'exit_code': 0,
            'construction_sha256': sha(self.root/'fallback.json'),
            'log': 'offline.log', 'log_sha256': sha(self.root/'offline.log')}
        with self.assertRaisesRegex(ValueError, 'compatibility receipt'):
            validate(self.root, self.entry, 'NRS-484B-127-1', 'C1', required=True)
        (self.root/'analysis.log').write_text('positive\n')
        (self.root/'negative.log').write_text('expected missing source\n')
        write(self.root/'compatibility.json', {
            'format': 'worker-package-compatibility-v2', 'passed': True,
            'case_id': self.case, 'candidate_id': 'fallback1',
            'construction_sha256': sha(self.root/'fallback.json'),
            'checks': ['selected_measurements', 'negative_case_source', 'lean_decoder', 'final_decode'],
            'log_sha256': sha(self.root/'analysis.log'),
            'negative_log_sha256': sha(self.root/'negative.log')})
        self.entry['candidates'][0]['compatibility'] = {
            'receipt': 'compatibility.json', 'sha256': sha(self.root/'compatibility.json'),
            'log': 'analysis.log', 'negative_log': 'negative.log'}
        self.assertEqual(validate(self.root, self.entry, 'NRS-484B-127-1', 'C1', required=True)['fallbacks'], ['fallback1'])
        (self.root/'negative.log').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'incomplete or changed'):
            validate(self.root, self.entry, 'NRS-484B-127-1', 'C1', required=True)

    def test_saved_processing_rejects_mismatched_selection_before_conversion(self):
        target = self.root/'attempt'
        materialize(self.root/'execution-manifest.json', self.case, target, 'fallback1')
        receipt = read(target/'candidate-selection.json')
        receipt['construction_sha256'] = '0' * 64
        write(target/'candidate-selection.json', receipt)
        with self.assertRaisesRegex(ValueError, 'candidate identity differs'):
            process_saved(self.root/'execution-manifest.json', self.case, target,
                          self.root/'processed', self.root/'library', self.root/'validator')


if __name__ == '__main__':
    unittest.main()
