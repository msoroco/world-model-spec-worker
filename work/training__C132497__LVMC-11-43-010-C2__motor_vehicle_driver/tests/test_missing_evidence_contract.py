"""Keep missing-source diagnostics from becoming completion evidence."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'c132497_missing_evidence_audit', ROOT/'native/audit_missing_evidence.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class MissingEvidenceContract(unittest.TestCase):
    def test_every_selected_config_carries_recording_description(self):
        for case in ('reference', 'contrast'):
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                with self.subTest(case=case, candidate=candidate):
                    package = json.loads((ROOT/'native/package-current'/case/candidate/
                                          'construction.json').read_text())
                    config = json.loads(next(item['content'] for item in package['files']
                                             if item['path'] == 'config.json'))
                    self.assertEqual(config['case']['recording_description'],
                                     package['recording_description'])

    def test_missing_actor_cannot_report_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            processing = root/'processing.json'
            result = root/'result.json'
            processing.write_text(json.dumps({'missing_evidence': True,
                'original_source_hashes': {'trace.jsonl': 'a'*64},
                'physical_acceptance_claimed': False}))
            result.write_text(json.dumps({'physical_checks': {'maneuver':
                {'status': 'met'}}, 'maneuver_completed': True, 'accepted': False}))
            receipt = json.loads(processing.read_text())
            receipt['result_sha256'] = hashlib.sha256(result.read_bytes()).hexdigest()
            processing.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'cannot complete'):
                AUDIT.audit(processing, result)
            result.write_text(json.dumps({'physical_checks': {'maneuver':
                {'status': 'unverified'}}, 'maneuver_completed': False,
                'accepted': False}))
            receipt['result_sha256'] = hashlib.sha256(result.read_bytes()).hexdigest()
            processing.write_text(json.dumps(receipt))
            self.assertTrue(AUDIT.audit(processing, result)
                            ['missing_evidence_rejected_as_completion'])


if __name__ == '__main__':
    unittest.main()
