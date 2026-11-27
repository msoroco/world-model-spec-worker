import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_outside_lane import m as outside, rows

folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(folder))
spec = importlib.util.spec_from_file_location('comparison_audit_c147331', folder / 'comparison_audit.py')
comparison = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = comparison
spec.loader.exec_module(comparison)


class Tests(unittest.TestCase):
    def test_source_bound_pair_and_negative_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left, right = root / 'left.jsonl', root / 'right.jsonl'
            a = rows(outside.CASES[0], 900)
            b = rows(outside.CASES[1], 900)
            for sequence in (a, b):
                for row in sequence:
                    row['capture_packet_sha256'] = 'packet'
            def write():
                for path, sequence in ((left, a), (right, b)):
                    path.write_text(''.join(json.dumps(row) + '\n' for row in sequence))
                return [sha256(path.read_bytes()).hexdigest() for path in (left, right)]
            digests = write()
            receipt = comparison.audit(folder / 'case-plan.json', 'north_entrance_vs_stay',
                                       [left, right], digests, 'map-source')
            self.assertTrue(receipt['source_isolation_passed'])
            b[100]['map_sha256'] = 'different'
            digests = write()
            with self.assertRaisesRegex(ValueError, 'fixed Native source changed'):
                comparison.audit(folder / 'case-plan.json', 'north_entrance_vs_stay',
                                 [left, right], digests, 'map-source')
            b[100]['map_sha256'] = 'map-source'
            for row in b:
                row['vehicle_class'] = 'qualifying_484b587_3'
            digests = write()
            with self.assertRaisesRegex(ValueError, 'undeclared comparison change: vehicle_class'):
                comparison.audit(folder / 'case-plan.json', 'north_entrance_vs_stay',
                                 [left, right], digests, 'map-source')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                comparison.audit(folder / 'case-plan.json', 'north_entrance_vs_stay',
                                 [left, right], ['0'*64, digests[1]], 'map-source')
