import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import audit
from yield_view_measurement import ASSIGNMENT


class DeliveryIndexTests(unittest.TestCase):
    def packet(self, root):
        plan = json.loads((Path(__file__).resolve().parents[1] / 'case-plan.json').read_text())
        cases = {}
        for case in plan['cases']:
            folder = root / case['case_id'].split('__')[-1]
            folder.mkdir()
            files = {}
            for key, name in [('context', 'context.json'), ('trace', 'original-trace.jsonl'),
                              ('receipt', 'receipt.json'), ('camera_manifest', 'cameras.json'),
                              ('measurement', 'measurement.json'),
                              ('comparison_packet', 'comparison-packet.json'),
                              ('reviewed_site', 'reviewed-site.json'),
                              ('reviewed_source_index', 'reviewed-sources.json')]:
                path = folder / name
                payload = {'legal_hazard_judgment': None} if key == 'measurement' else {'key': key}
                path.write_text(json.dumps(payload) + '\n')
                files[key] = {'path': str(path.relative_to(root)),
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            cases[case['case_id']] = files
        index = root / 'index.json'
        index.write_text(json.dumps({'assignment_id': ASSIGNMENT,
                                     'source_kind': 'original_native_delivery',
                                     'cases': cases}) + '\n')
        return index

    def test_exact_three_case_two_comparison_source_index(self):
        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as tmp:
            index = self.packet(Path(tmp))
            with patch('delivery_audit.finalize', return_value={'legal_hazard_judgment': None}), \
                    patch('delivery_audit.compare_original', return_value={'review_limit': 'unresolved'}):
                result = audit(index)
            self.assertEqual((result['case_count'], result['comparison_count']), (3, 2))
            self.assertEqual(result['physical_acceptance'], 'unverified')

    def test_changed_original_packet_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as tmp:
            index = self.packet(Path(tmp))
            original = Path(tmp) / 'yield_slow_hazard' / 'original-trace.jsonl'
            original.write_text('{"changed": true}\n')
            with self.assertRaisesRegex(ValueError, 'original yield source changed'):
                audit(index)


if __name__ == '__main__':
    unittest.main()
