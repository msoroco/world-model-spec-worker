import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from approaching_comparison_audit import compare


class ApproachingComparisonTests(unittest.TestCase):
    def test_rejects_changed_fixed_opposing_trajectory(self):
        y = ROOT / 'cases/approaching_yield/diagnostic.json'
        data = json.loads((ROOT / 'cases/approaching_no_yield/diagnostic.json').read_text())
        rows = [json.loads(line) for line in data['files']['interaction_history.jsonl'].splitlines() if line]
        rows[1]['oncoming']['position_xy_m'][0] += 1.0
        data['files']['interaction_history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / 'changed.json'
            changed.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Fixed opposing actor trajectory differs: oncoming'):
                compare(y, changed)


if __name__ == '__main__':
    unittest.main()
