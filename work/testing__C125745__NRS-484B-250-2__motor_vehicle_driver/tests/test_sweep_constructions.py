import hashlib
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((HERE / path).read_text())


def digest(path):
    return hashlib.sha256((HERE / path).read_bytes()).hexdigest()


class SweepConstructionTests(unittest.TestCase):
    def test_exact_commanded_axes_and_distinct_offline_fallbacks(self):
        index = read('sweep-constructions/index.json')
        self.assertEqual(len(index['constructions']), 6)
        for row in index['constructions']:
            with self.subTest(case=row['case_id']):
                primary = read(row['construction'])
                self.assertEqual(digest(row['construction']), row['sha256'])
                axis = row['sweep_point']['axis']
                value = row['sweep_point']['commanded_value']
                config = json.loads(next(f['content'] for f in primary['files']
                                         if f['path'] == 'config.json'))
                self.assertEqual(primary['case_id'], row['case_id'])
                self.assertEqual(config['selected_case_id'], row['case_id'])
                self.assertEqual(config[axis], value)
                self.assertEqual(primary['sweep_point'], row['sweep_point'])
                constructions = {row['sha256']}
                for candidate_id in ('fallback1', 'fallback2', 'fallback3'):
                    fallback = row[candidate_id]
                    self.assertEqual(fallback['status'], 'offline_proven')
                    self.assertEqual(digest(fallback['construction']),
                                     fallback['construction_sha256'])
                    constructions.add(fallback['construction_sha256'])
                    alternate = read(fallback['construction'])
                    self.assertEqual(alternate['case_id'], row['case_id'])
                    self.assertEqual(alternate['recording_description'],
                                     primary['recording_description'])
                    alternate_config = json.loads(next(f['content'] for f in alternate['files']
                                                       if f['path'] == 'config.json'))
                    self.assertEqual(alternate_config['selected_case_id'], row['case_id'])
                    proof = fallback['offline']
                    self.assertEqual(proof['exit_code'], 0)
                    self.assertEqual(digest(proof['log']), proof['log_sha256'])
                    log = (HERE / proof['log']).read_text()
                    self.assertIn(f"CASE {row['case_id']}", log)
                    self.assertIn('COMMAND ' + proof['command'], log)
                    self.assertIn('EXIT 0', log)
                self.assertEqual(len(constructions), 4)
                receipt = row['current_runtime_proof']['positive_compatibility_receipt']
                self.assertEqual(digest(receipt['file']), receipt['sha256'])
                self.assertEqual(read(receipt['file'])['construction_sha256'], row['sha256'])
                saved = row['current_runtime_proof']['recorded_only_saved_receipt']
                self.assertEqual(digest(saved['file']), saved['sha256'])
                self.assertTrue(read(saved['file'])['recorded_only'])
