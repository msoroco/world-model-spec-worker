"""Exercise provenance joins and a changed fixed source after saved processing."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from saved_comparison_audit import audit


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


class SavedComparisonAuditTest(unittest.TestCase):
    def test_current_saved_comparisons(self):
        result = audit(HERE)
        self.assertEqual(len(result['comparisons']), 6)
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_changed_fixed_source_is_rejected_even_with_rehashed_receipt(self):
        with tempfile.TemporaryDirectory(prefix='c111603-saved-audit-') as tmp:
            folder = Path(tmp) / HERE.name
            folder.mkdir()
            for name in ('execution-manifest.json', 'case-plan.json',
                         'comparison-proof-index.json', 'comparison_audit.py'):
                shutil.copy2(HERE / name, folder / name)
            index = json.loads((HERE / 'aggregate-saved/index.json').read_text())
            for row in index['cases']:
                for name in ('receipt', 'log'):
                    dest = folder / row[name]
                    dest.parent.mkdir(exist_ok=True)
                    shutil.copy2(HERE / row[name], dest)
            for row in json.loads((HERE / 'comparison-proof-index.json').read_text())['comparisons']:
                for name in ('receipt', 'log'):
                    shutil.copy2(HERE / row[name], folder / row[name])
            target = index['cases'][0]
            path = folder / target['receipt']
            receipt = json.loads(path.read_text())
            receipt['original_source_hashes']['ego_turn_motion.jsonl'] = '0' * 64
            write(path, receipt)
            target['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            write(folder / 'aggregate-saved/index.json', index)
            with self.assertRaisesRegex(ValueError, 'Saved fixed source changed'):
                audit(folder)


if __name__ == '__main__':
    unittest.main()
