import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_bus_curb import probe, rows, scene

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from delivery_audit import audit_comparisons
from reviewed_source import FIELDS


class DeliveryAuditTests(unittest.TestCase):
    def test_all_diagnostic_boundaries_without_legal_disposition(self):
        reports = {}
        for case in probe.CASES:
            measured = probe.measure_original(rows(case, scene(case)), scene(case), case)
            self.assertIsNone(measured['parallel_judgment'])
            self.assertIsNone(measured['unduly_impede_judgment'])
            reports[root.name + '__' + case.name] = {
                'format': 'c149470-independent-original-attempt-audit-v1',
                'case_id': root.name + '__' + case.name,
                'source_kind': 'synthetic_diagnostic_fixture',
                'measurement': measured}
        with self.assertRaisesRegex(ValueError, 'nonoriginal'):
            audit_comparisons(reports)

    def test_original_audit_requires_reviewed_packet(self):
        from delivery_audit import audit_attempt
        with self.assertRaisesRegex(ValueError, 'missing'):
            audit_attempt(root / 'absent-site.json', root / 'absent-attempt',
                          probe.CASES[0].name)

    def test_synthetic_scene_cannot_claim_reviewed_site(self):
        from reviewed_source import verify
        construction = json.loads((root / 'construction-diagnostic-bus_stop_below.json').read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        synthetic = json.loads(files['scene.json'])
        scratch = root.parents[1] / '.runtime-work' / 'c149470' / 'tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            packet = Path(temp) / 'site.json'
            packet.write_text(json.dumps({'format': 'c149470-reviewed-site-v1',
                                          'review_status': 'reviewed',
                                          'reviewer': 'synthetic-test',
                                          'scene': synthetic,
                                          'source_bindings': {}}))
            with self.assertRaisesRegex(ValueError, 'provenance'):
                verify(packet, 'bus_stop_below')

    def test_saved_finalizer_is_recorded_only(self):
        from saved_finalizer import finalize
        with self.assertRaisesRegex(ValueError, 'reviewed.*missing'):
            finalize(root / 'absent-attempt', root / 'diagnostic-source-note.json',
                     'bus_stop_below')

    def test_comparison_rejects_changed_fixed_source(self):
        # In-memory mock reports exercise rejection only; no original claim is emitted.
        reports = {}
        for case in probe.CASES:
            hashes = {name: 'a' * 64 for name in FIELDS}
            measured = probe.measure_original(rows(case, scene(case)), scene(case), case)
            measured['source_hashes'] = hashes
            reports[root.name + '__' + case.name] = {
                'format': 'c149470-independent-original-attempt-audit-v1',
                'case_id': root.name + '__' + case.name,
                'source_kind': 'original_native_capture',
                'legal_status': 'unresolved', 'physical_acceptance': False,
                'source_hashes': hashes, 'measurement': measured}
        reports[root.name + '__bus_stop_at']['source_hashes']['curb_geometry'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'fixed original source changed'):
            audit_comparisons(reports)


if __name__ == '__main__':
    unittest.main()
