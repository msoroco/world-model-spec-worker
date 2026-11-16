import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from approaching_comparison_audit import check_fixed_config, compare
from inside_comparison_audit import check_fixed_construction


class ApproachingComparisonTests(unittest.TestCase):
    def test_approaching_pair_rejects_undeclared_config_change(self):
        case_root = ROOT / 'cases'
        yield_config = json.loads((case_root / 'approaching_yield/config.json').read_text())
        no_yield_config = json.loads((case_root / 'approaching_no_yield/config.json').read_text())
        check_fixed_config(yield_config, no_yield_config)
        altered = dict(no_yield_config, duration_s=46)
        with self.assertRaisesRegex(ValueError, 'Fixed full construction configuration differs'):
            check_fixed_config(yield_config, altered)

    def test_inside_pair_rejects_unrelated_construction_change(self):
        def embedded(name):
            case = ROOT / 'cases' / name
            bundle = json.loads((case / 'construction.json').read_text())
            files = {item['path']: item['content'] for item in bundle['files']}
            return files, json.loads((case / 'config.json').read_text())

        yield_files, yield_config = embedded('inside_yield')
        no_yield_files, no_yield_config = embedded('inside_no_yield')
        check_fixed_construction(yield_files, no_yield_files, yield_config, no_yield_config)
        changed = dict(no_yield_files, **{'camera_setup.py': no_yield_files['camera_setup.py'] + '\n# altered\n'})
        with self.assertRaisesRegex(ValueError, 'Fixed shared construction differs: camera_setup.py'):
            check_fixed_construction(yield_files, changed, yield_config, no_yield_config)
        changed_config = dict(no_yield_config, approach_speed_mps=no_yield_config['approach_speed_mps'] + 1)
        with self.assertRaisesRegex(ValueError, 'Fixed construction configuration differs'):
            check_fixed_construction(yield_files, no_yield_files, yield_config, changed_config)

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
