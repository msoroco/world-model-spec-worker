import base64
import hashlib
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((HERE / path).read_text())


def digest(path):
    return hashlib.sha256((HERE / path).read_bytes()).hexdigest()


def indexed_log(proof):
    if 'log_member' not in proof:
        return (HERE / proof['log']).read_text()
    archive = json.loads((HERE / proof['log']).read_text())
    member = archive['files'][proof['log_member']]
    data = base64.b64decode(member['base64'], validate=True)
    assert hashlib.sha256(data).hexdigest() == member['sha256']
    assert member['sha256'] == proof['original_log_sha256']
    return data.decode()


def indexed_file_json(spec):
    if 'archive_member' not in spec:
        return read(spec['file'])
    archive = read(spec['file'])
    member = archive['files'][spec['archive_member']]
    data = base64.b64decode(member['base64'], validate=True)
    assert hashlib.sha256(data).hexdigest() == member['sha256']
    assert member['sha256'] == spec['original_sha256']
    return json.loads(data)


class SweepConstructionTests(unittest.TestCase):
    def test_first_timing_point_qualified_fallback_payloads(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0000')
        full_id = HERE.name + '__c125745-1-0000'
        proof = row['qualified_fallbacks']
        self.assertEqual([item['id'] for item in proof['candidates']],
                         ['fallback1', 'fallback2', 'fallback3'])
        hashes = set()
        for item in proof['candidates']:
            with self.subTest(candidate=item['id']):
                payload = item['construction_payload'].encode()
                self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                 item['construction_sha256'])
                bundle = json.loads(payload)
                config = json.loads(next(file['content'] for file in bundle['files']
                                         if file['path'] == 'config.json'))
                self.assertEqual(bundle['case_id'], full_id)
                self.assertEqual(config['selected_case_id'], full_id)
                self.assertEqual(bundle['recording_description'],
                                 json.loads((HERE / row['qualified_primary']['construction']).read_text())['recording_description'])
                self.assertEqual(hashlib.sha256(item['offline_log_payload'].encode()).hexdigest(),
                                 item['offline_log_sha256'])
                self.assertEqual(item['offline_exit_code'], 0)
                self.assertFalse(item['offline_simulation_started'])
                hashes.add(item['construction_sha256'])
        self.assertEqual(len(hashes), 3)

    def test_staged_physical_classifier_archive(self):
        index = read('sweep-constructions/index.json')
        for row in index['constructions']:
            with self.subTest(case=row['case_id']):
                proof = row['staged_physical_cpu_proof']
                self.assertIn('synthetic classifier', proof['scope'])
                self.assertEqual(digest(proof['archive_file']), proof['archive_sha256'])
                archive = read(proof['archive_file'])
                for kind, expected in [('complete_motion', 'met'),
                                       ('incomplete_motion', 'not_met'),
                                       ('missing_evidence', 'unverified')]:
                    binding = proof['fixtures']['json_' + kind]
                    item = archive['files'][binding['archive_member']]
                    data = base64.b64decode(item['base64'], validate=True)
                    self.assertEqual(hashlib.sha256(data).hexdigest(), binding['original_sha256'])
                    result = json.loads(data)
                    self.assertEqual(result['physical_checks']['maneuver']['status'], expected)
                    self.assertEqual(result['maneuver_completed'], expected == 'met')
                    self.assertFalse(result['physical_acceptance_claimed'])

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
                    log = indexed_log(proof)
                    self.assertIn(f"CASE {row['case_id']}", log)
                    self.assertIn('COMMAND ' + proof['command'], log)
                    self.assertIn('EXIT 0', log)
                self.assertEqual(len(constructions), 4)
                receipt = row['current_runtime_proof']['positive_compatibility_receipt']
                self.assertEqual(digest(receipt['file']), receipt['sha256'])
                self.assertEqual(indexed_file_json(receipt)['construction_sha256'], row['sha256'])
                saved = row['current_runtime_proof']['recorded_only_saved_receipt']
                self.assertEqual(digest(saved['file']), saved['sha256'])
                self.assertTrue(indexed_file_json(saved)['recorded_only'])

    def test_archived_candidate_receipts_bind_exact_constructions(self):
        index = read('sweep-constructions/index.json')
        root = HERE.parent
        for candidate_id in ('fallback1', 'fallback2', 'fallback3'):
            archive_path = root / '_shared' / f'c125745-sweep-{candidate_id}-proofs-2026-11-23.json'
            archive = json.loads(archive_path.read_text())
            for row in index['constructions']:
                with self.subTest(case=row['case_id'], candidate=candidate_id):
                    fallback = row[candidate_id]
                    proof = fallback['current_runtime_proof']
                    self.assertEqual(proof['status'], 'positive_negative_and_saved_passed')
                    members = archive['members'][row['case_id']]
                    decoded = {}
                    for name, item in members.items():
                        data = base64.b64decode(item['base64'], validate=True)
                        self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
                        decoded[name] = data
                    receipt = json.loads(decoded['positive_receipt'])
                    saved = json.loads(decoded['recorded_only_receipt'])
                    self.assertEqual(receipt['construction_sha256'], fallback['construction_sha256'])
                    self.assertEqual(receipt['candidate_id'], candidate_id)
                    self.assertTrue(receipt['passed'])
                    self.assertEqual(receipt['log_sha256'], members['positive_analysis_log']['sha256'])
                    self.assertEqual(receipt['negative_log_sha256'], members['negative_analysis_log']['sha256'])
                    self.assertEqual(saved['native_revision']['construction_sha256'], fallback['construction_sha256'])
                    self.assertTrue(saved['recorded_only'])
