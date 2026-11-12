import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_safety_comparison import audit

ROOT = Path(__file__).resolve().parents[1]


class SafetyComparisonTests(unittest.TestCase):
    def test_fixed_conditions_and_declared_difference(self):
        result = audit(ROOT/'construction.json', ROOT/'construction-safety_conflict.json',
                       ROOT/'diagnostic-safety_clear.json',
                       ROOT/'diagnostic-safety_conflict.json')
        self.assertEqual(result['diagnostic_oncoming_x_separation_m'], 8)
        self.assertIsNone(result['legal_safety_verdict'])

    def test_rejects_uncontrolled_camera_and_actor_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = json.loads((ROOT/'construction-safety_conflict.json').read_text())
            config = next(item for item in source['files'] if item['path'] == 'config.json')
            data = json.loads(config['content'])
            data['cameras'][0]['fov_deg'] += 1
            config['content'] = json.dumps(data)
            altered = Path(directory)/'construction.json'
            altered.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, 'Fixed U-turn comparison changed: cameras'):
                audit(ROOT/'construction.json', altered,
                      ROOT/'diagnostic-safety_clear.json',
                      ROOT/'diagnostic-safety_conflict.json')
            fixture = json.loads((ROOT/'diagnostic-safety_conflict.json').read_text())
            rows = [json.loads(x) for x in fixture['files']['u_turn_motion.jsonl'].splitlines()]
            rows[1]['participants']['3']['speed_mps'] += 1
            fixture['files']['u_turn_motion.jsonl'] = ''.join(json.dumps(x)+'\n' for x in rows)
            changed = Path(directory)/'diagnostic.json'
            changed.write_text(json.dumps(fixture))
            with self.assertRaisesRegex(ValueError, 'Uncontrolled original U-turn actor difference'):
                audit(ROOT/'construction.json', ROOT/'construction-safety_conflict.json',
                      ROOT/'diagnostic-safety_clear.json', changed)


if __name__ == '__main__':
    unittest.main()
