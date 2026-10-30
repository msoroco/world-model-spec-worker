"""Regression for exact retained-case saved-only command binding."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime/main-pipeline-v1/scenario_pipeline'))
from worker_exchange.common import sha, write
from worker_exchange.preparation import check_legacy_capture_handoff


class LegacyHandoffTests(unittest.TestCase):
    def test_exact_case_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            case = 'testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__selected_left_turn'
            input_path = 'inputs/legacy-captures/case.json'
            report_path = 'work/_shared/retained-c109705-handoff.json'
            manifest_path = 'work/_shared/legacy-captures/case/execution-manifest.json'
            folder = repo / 'work/_shared/legacy-captures/case'
            folder.mkdir(parents=True)
            write(repo / input_path, {'format': 'worker-legacy-capture-contract-v1', 'case_id': case,
                                      'frames': 900, 'original_construction_sha256': 'a' * 64})
            write(folder / 'construction.json', {'case_id': case})
            write(folder / 'proposals/cases.json', {'cases': [{'case_id': case}]})
            write(folder / 'execution-manifest.json', {'cases': [{
                'case_id': case, 'native_construction_sha256': 'a' * 64,
                'construction': 'construction.json', 'construction_sha256': sha(folder / 'construction.json'),
                'measurement_procedure': {'entrypoint': 'analyze.py'}}]})
            log = folder / 'proof.log'; log.write_text('900-frame synthetic saved-only test passed\n')
            report = {'format': 'worker-legacy-saved-handoff-v1', 'case_id': case,
                      'original_construction_sha256': 'a' * 64, 'manifest': manifest_path,
                      'actual_recording_audited': False, 'native_replay_requested': False,
                      'saved_only_audit_command': 'python3.11 runtime.py process-saved --manifest '
                                                  + manifest_path + ' --case ' + case
                                                  + ' --attempt "$RETAINED_C109705_ATTEMPT"',
                      'diagnostic_proof': {'case_id': case, 'frames': 900, 'exit_code': 0,
                                           'log': 'work/_shared/legacy-captures/case/proof.log',
                                           'log_sha256': sha(log)}}
            write(repo / report_path, report)
            contract = {'input': input_path, 'report': report_path}
            check_legacy_capture_handoff(repo, contract)
            report['saved_only_audit_command'] = report['saved_only_audit_command'].replace(
                case, case.replace('selected_left_turn', 'near_centerline'))
            write(repo / report_path, report)
            with self.assertRaisesRegex(ValueError, 'selects another case'):
                check_legacy_capture_handoff(repo, contract)


if __name__ == '__main__':
    unittest.main()
