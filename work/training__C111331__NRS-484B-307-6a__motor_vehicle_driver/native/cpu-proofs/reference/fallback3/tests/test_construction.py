import copy
import json
from pathlib import Path
import unittest
import runner

class ExactRequestTests(unittest.TestCase):
    def test_exact_request(self):
        result = runner.check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['request_rows'], 480)
        self.assertFalse(result['carla_imported'])
        self.assertFalse(result['physical_success_claimed'])

    def test_request_corruption_rejected(self):
        path = Path('native-requests.jsonl')
        original = path.read_text()
        try:
            rows = [json.loads(line) for line in original.splitlines()]
            rows[200]['signal_phase_requested'] = 'green'
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                runner.check()
        finally:
            path.write_text(original)

    def test_observation_claim_rejected(self):
        path = Path('config.json')
        original = path.read_text()
        try:
            config = json.loads(original)
            config['no_native_or_original_observation_claimed'] = False
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'Physical evidence claimed'):
                runner.check()
        finally:
            path.write_text(original)

if __name__ == '__main__': unittest.main()
