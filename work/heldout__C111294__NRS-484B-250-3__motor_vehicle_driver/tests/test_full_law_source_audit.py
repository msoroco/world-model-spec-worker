import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from audit_full_law_delivery import audit


class FullLawSourceAuditTests(unittest.TestCase):
    def test_current_exact_source_bindings(self):
        report = audit()
        self.assertEqual(report['local_selected_cases'], 9)
        self.assertEqual(report['local_comparisons'], 6)
        self.assertFalse(report['physical_or_legal_acceptance_claimed'])

    def test_rejects_swapped_source_identity_and_stale_queue(self):
        matrix = json.loads((HERE / 'qualitative-source-matrix-proof.json').read_text())
        matrix['turn_case'] = matrix['ending_case']
        with self.assertRaisesRegex(ValueError, 'opposing-left selected source'):
            audit(matrix=matrix)
        queue = json.loads((HERE / 'gpu-queue.json').read_text())
        queue['execution_manifest_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'queue source hashes differ'):
            audit(queue=queue)


if __name__ == '__main__':
    unittest.main()
