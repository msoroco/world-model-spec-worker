import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from listener_sweep_audit import audit


class ListenerSweepAuditTests(unittest.TestCase):
    def test_source_bound_three_point_sweep(self):
        result = audit()
        self.assertEqual([row['offset_m'] for row in result['points']], [2, 4, 6])
        self.assertFalse(result['physical_audibility_verified'])

    def test_rejects_changed_listener_position_and_frame(self):
        source = json.loads((HERE / 'listener-4m-diagnostic.json').read_text())
        rows = [json.loads(line) for line in source['files']['participant_bodies.jsonl'].splitlines()]
        rows[0]['bodies']['ped_listener']['y_m'] = 5
        altered = ''.join(json.dumps(row) + '\n' for row in rows)
        with self.assertRaisesRegex(ValueError, 'point differs'):
            audit(source_override={4: {'participant_bodies.jsonl': altered}})
        rows[0]['bodies']['ped_listener']['y_m'] = 4
        rows[0]['frame'] += 1
        altered = ''.join(json.dumps(row) + '\n' for row in rows)
        with self.assertRaisesRegex(ValueError, 'Misjoined'):
            audit(source_override={4: {'participant_bodies.jsonl': altered}})


if __name__ == '__main__':
    unittest.main()
