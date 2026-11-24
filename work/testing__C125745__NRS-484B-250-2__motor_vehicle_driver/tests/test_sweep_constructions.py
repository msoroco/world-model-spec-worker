import base64
import hashlib
import json
import tarfile
import unittest
import zlib
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
HISTORY = HERE.parent / '_shared' / 'cpu-proof-history-20261123.tar.xz'
NESTED_SHA256 = {
    'c125745-stale-axis-diagnostics-2026-11-23.json': 'af55976737ce91916ed74698733b4f785e1604ff4fe6d396efff0a3ce3f72772',
    'c125745-sweep-fallback1-proofs-2026-11-23.json': 'cfd2e8ca423c4627a6dbec3ab9a7f30969082aa653c6247d1c56c3feea5a2c32',
    'c125745-sweep-fallback2-proofs-2026-11-23.json': 'dd40fda9a721cb3f5766e52857650636b3edc1066800472b5e94d0f0d7b2719d',
}


def source_bytes(path):
    source = HERE / path
    if source.is_file():
        return source.read_bytes()
    name = source.name
    if name not in NESTED_SHA256 or source.parent.resolve() != HISTORY.parent:
        raise FileNotFoundError(source)
    with tarfile.open(HISTORY, 'r:xz') as packed:
        member = packed.extractfile(name)
        assert member is not None
        data = member.read()
    assert hashlib.sha256(data).hexdigest() == NESTED_SHA256[name]
    return data


def read(path):
    return json.loads(source_bytes(path))


def digest(path):
    return hashlib.sha256(source_bytes(path)).hexdigest()


def construction_bytes(item):
    if 'construction_zlib_base64' in item:
        payload = zlib.decompress(base64.b64decode(
            item['construction_zlib_base64'], validate=True))
        assert len(payload) == item['construction_bytes']
        return payload
    return item['construction_payload'].encode()


def historical_bytes(item):
    archive_path = HERE / item['historical_construction_archive']
    if archive_path.suffix == '.xz':
        with tarfile.open(archive_path, 'r:xz') as packed:
            source = packed.extractfile(
                'work/testing__C125745__NRS-484B-250-2__motor_vehicle_driver/'
                'sweep-constructions/historical-unqualified-bundles.json')
            archive = json.load(source)
    else:
        archive = json.loads(archive_path.read_text())
    member = archive['files'][item['historical_construction_member']]
    raw = zlib.decompress(base64.b64decode(member['zlib_base64'], validate=True))
    assert len(raw) == member['bytes']
    assert hashlib.sha256(raw).hexdigest() == member['sha256']
    return raw


def proof_text(item, field):
    key = field + '_payload'
    if key in item:
        return item[key]
    raw = zlib.decompress(base64.b64decode(
        item[field + '_zlib_base64'], validate=True))
    assert len(raw) == item[field + '_bytes']
    return raw.decode()


def indexed_log(proof):
    if 'log_member' not in proof:
        return source_bytes(proof['log']).decode()
    archive = json.loads(source_bytes(proof['log']))
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
    def test_returned_manifest_materializes_all_qualified_sweep_bundles(self):
        index = read('sweep-constructions/index.json')
        manifest = read('execution-manifest.json')
        selected = {item['case_id']: item for item in manifest['cases']}
        for row in index['constructions']:
            primary = row['qualified_primary']
            entry = selected[primary['case_id']]
            self.assertEqual(entry['construction'], primary['construction'])
            self.assertEqual(entry['construction_sha256'], primary['construction_sha256'])
            cases = [('primary', primary, entry)]
            candidates = {item['id']: item for item in entry['candidates']}
            for item in row['qualified_fallbacks']['candidates']:
                cases.append((item['id'], item, candidates[item['id']]))
            for name, qualified, bound in cases:
                with self.subTest(case=row['case_id'], candidate=name):
                    raw = (HERE / qualified['construction']).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),
                                     qualified['construction_sha256'])
                    self.assertEqual(bound['construction'], qualified['construction'])
                    self.assertEqual(bound['construction_sha256'],
                                     qualified['construction_sha256'])
                    offline = qualified['canonical_offline_proof']
                    self.assertEqual(offline['exit_code'], 0)
                    self.assertFalse(offline['simulation_started'])
                    self.assertEqual(offline['construction_sha256'],
                                     qualified['construction_sha256'])
                    self.assertEqual(bound['offline_evidence'], offline)
                    log = index['canonical_offline_logs'][offline['log_sha256']]
                    self.assertEqual(hashlib.sha256(log.encode()).hexdigest(),
                                     offline['log_sha256'])
                    self.assertIn('Ran 1 test', log)
                    self.assertIn('offline', bound)
                    standalone = bound['offline']
                    self.assertEqual(standalone['construction_sha256'],
                                     offline['construction_sha256'])
                    self.assertEqual(standalone['command'], offline['command'])
                    self.assertEqual(standalone['exit_code'], 0)
                    self.assertEqual(standalone['log_sha256'],
                                     offline['log_sha256'])
                    self.assertEqual((HERE / standalone['log']).read_text(), log)
                    old = row if name == 'primary' else row[name]
                    historical = historical_bytes(old)
                    self.assertEqual(hashlib.sha256(historical).hexdigest(),
                                     old.get('construction_sha256', old.get('sha256')))

    def test_qualified_hold_fallback_matrices(self):
        index = read('sweep-constructions/index.json')
        expected = {'c125745-2-0000': 0, 'c125745-2-0002': 8,
                    'c125745-2-0001': 16}
        for short, hold in expected.items():
            row = next(item for item in index['constructions']
                       if item['case_id'] == short)
            items = row['qualified_fallbacks']['candidates']
            self.assertEqual([item['id'] for item in items],
                             ['fallback1', 'fallback2', 'fallback3'])
            self.assertEqual([item['changed_knobs'] for item in items],
                             [['ego_hold_after_clear_frames'],
                              ['site.camera_poses.overview'],
                              ['site.approaches.other.route_xy_m']])
            self.assertEqual(len({item['construction_sha256'] for item in items}), 3)
            for item in items:
                with self.subTest(case=short, candidate=item['id']):
                    raw = construction_bytes(item)
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),
                                     item['construction_sha256'])
                    bundle = json.loads(raw)
                    config = json.loads(next(f['content'] for f in bundle['files']
                                             if f['path'] == 'config.json'))
                    self.assertEqual(bundle['case_id'], item['case_id'])
                    self.assertEqual(bundle['candidate_id'], item['id'])
                    self.assertEqual(config['selected_case_id'], item['case_id'])
                    self.assertEqual(config['ego_hold_after_clear_frames'],
                                     hold + 4 if item['id'] == 'fallback1' else hold)
                    offline = item['offline']
                    self.assertEqual(offline['exit_code'], 0)
                    self.assertFalse(offline['simulation_started'])
                    for field in ('log', 'command_log'):
                        payload = offline[field + '_payload'].encode()
                        self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                         offline[field + '_sha256'])
                    self.assertTrue(json.loads(offline['command_log_payload'])
                                    ['offline_passed'])
                    proof = item['current_runtime_proof']
                    positive = proof['positive_compatibility']
                    negative = proof['negative_compatibility']
                    saved = proof['recorded_only_saved']
                    for binding in (positive, saved):
                        self.assertEqual(binding['exit_code'], 0)
                        for field in ('receipt', 'analysis_log'):
                            payload = proof_text(binding, field).encode()
                            self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                             binding[field + '_sha256'])
                    self.assertEqual(hashlib.sha256(negative['log_payload'].encode()).hexdigest(),
                                     negative['log_sha256'])
                    compat = json.loads(proof_text(positive, 'receipt'))
                    processed = json.loads(proof_text(saved, 'receipt'))
                    self.assertTrue(compat['passed'])
                    self.assertEqual(compat['candidate_id'], item['id'])
                    self.assertEqual(compat['construction_sha256'],
                                     item['construction_sha256'])
                    self.assertEqual(compat['negative_log_sha256'],
                                     negative['log_sha256'])
                    self.assertTrue(processed['passed'])
                    self.assertTrue(processed['recorded_only'])
                    self.assertTrue(processed['originals_preserved'])
                    self.assertEqual(processed['candidate_id'], item['id'])
                    self.assertEqual(processed['native_revision']['construction_sha256'],
                                     item['construction_sha256'])
                    self.assertFalse(processed['physical_acceptance_claimed'])
                    self.assertFalse(processed['legal_acceptance_claimed'])
                    physical = item['physical_cpu_proof']
                    self.assertEqual(physical['saved_processing_receipt_sha256'],
                                     saved['receipt_sha256'])
                    for name, binding in physical['fixtures'].items():
                        data = zlib.decompress(base64.b64decode(
                            binding['payload_zlib_base64'], validate=True))
                        self.assertEqual(len(data), binding['uncompressed_bytes'])
                        self.assertEqual(hashlib.sha256(data).hexdigest(), binding['sha256'])
                        if name == 'lifecycle_json':
                            life = json.loads(data)
                            self.assertEqual(life['saved_processing_receipt_sha256'],
                                             saved['receipt_sha256'])
                            self.assertTrue(life['failed_encoder_rejected'])
                            self.assertTrue(life['premature_release_rejected'])
                    self.assertTrue(all(code == 0 for code in
                                        physical['exit_codes'].values()))

    def test_frame_48_qualified_fallback_matrix(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0001')
        items = row['qualified_fallbacks']['candidates']
        self.assertEqual([item['id'] for item in items],
                         ['fallback1', 'fallback2', 'fallback3'])
        self.assertEqual([item['changed_knobs'] for item in items],
                         [['other_release_frame'], ['site.camera_poses.overview'],
                          ['site.approaches.other.route_xy_m']])
        self.assertEqual(len({item['construction_sha256'] for item in items}), 3)
        for item in items:
            with self.subTest(candidate=item['id']):
                raw = construction_bytes(item)
                self.assertEqual(hashlib.sha256(raw).hexdigest(),
                                 item['construction_sha256'])
                bundle = json.loads(raw)
                config = json.loads(next(f['content'] for f in bundle['files']
                                         if f['path'] == 'config.json'))
                self.assertEqual(bundle['case_id'], item['case_id'])
                self.assertEqual(bundle['candidate_id'], item['id'])
                self.assertEqual(config['selected_case_id'], item['case_id'])
                self.assertEqual(config['other_release_frame'],
                                 44 if item['id'] == 'fallback1' else 48)
                self.assertEqual(item['offline']['exit_code'], 0)
                self.assertFalse(item['offline']['simulation_started'])
                for field in ('log', 'command_log'):
                    payload = item['offline'][field + '_payload'].encode()
                    self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                     item['offline'][field + '_sha256'])
                self.assertTrue(json.loads(item['offline']['command_log_payload'])
                                ['offline_passed'])
                proof = item['current_runtime_proof']
                positive = proof['positive_compatibility']
                negative = proof['negative_compatibility']
                saved = proof['recorded_only_saved']
                for binding in (positive, saved):
                    self.assertEqual(binding['exit_code'], 0)
                    for field in ('receipt', 'analysis_log'):
                        payload = proof_text(binding, field).encode()
                        self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                         binding[field + '_sha256'])
                self.assertEqual(hashlib.sha256(negative['log_payload'].encode()).hexdigest(),
                                 negative['log_sha256'])
                compat = json.loads(proof_text(positive, 'receipt'))
                processed = json.loads(proof_text(saved, 'receipt'))
                self.assertTrue(compat['passed'])
                self.assertEqual(compat['candidate_id'], item['id'])
                self.assertEqual(compat['construction_sha256'],
                                 item['construction_sha256'])
                self.assertEqual(compat['negative_log_sha256'],
                                 negative['log_sha256'])
                self.assertTrue(processed['passed'])
                self.assertTrue(processed['recorded_only'])
                self.assertTrue(processed['originals_preserved'])
                self.assertEqual(processed['candidate_id'], item['id'])
                self.assertEqual(processed['native_revision']['construction_sha256'],
                                 item['construction_sha256'])
                self.assertFalse(processed['physical_acceptance_claimed'])
                self.assertFalse(processed['legal_acceptance_claimed'])
                physical = item['physical_cpu_proof']
                self.assertEqual(physical['saved_processing_receipt_sha256'],
                                 saved['receipt_sha256'])
                for name, binding in physical['fixtures'].items():
                    data = zlib.decompress(base64.b64decode(
                        binding['payload_zlib_base64'], validate=True))
                    self.assertEqual(len(data), binding['uncompressed_bytes'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), binding['sha256'])
                    if name.endswith('_json') and name != 'lifecycle_json':
                        self.assertFalse(json.loads(data)['physical_acceptance_claimed'])
                    if name == 'lifecycle_json':
                        life = json.loads(data)
                        self.assertEqual(life['saved_processing_receipt_sha256'],
                                         saved['receipt_sha256'])
                        self.assertTrue(life['failed_encoder_rejected'])
                        self.assertTrue(life['premature_release_rejected'])
                self.assertEqual(set(physical['exit_codes']),
                                 {'complete_motion', 'incomplete_motion',
                                  'missing_evidence', 'lifecycle'})
                self.assertTrue(all(code == 0 for code in physical['exit_codes'].values()))

    def test_qualified_hold_primary_current_runtime_and_physical_proofs(self):
        index = read('sweep-constructions/index.json')
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}
        for short in ('c125745-2-0000', 'c125745-2-0002', 'c125745-2-0001'):
            row = next(item for item in index['constructions']
                       if item['case_id'] == short)
            item = row['qualified_primary']
            with self.subTest(case=short):
                proof = item['current_runtime_proof']
                positive = proof['positive_compatibility']
                negative = proof['negative_compatibility']
                saved = proof['recorded_only_saved']
                for binding in (positive, saved):
                    self.assertEqual(binding['exit_code'], 0)
                    for field in ('receipt', 'analysis_log'):
                        raw = proof_text(binding, field).encode()
                        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                                         binding[field + '_sha256'])
                self.assertEqual(hashlib.sha256(negative['log_payload'].encode()).hexdigest(),
                                 negative['log_sha256'])
                compat = json.loads(proof_text(positive, 'receipt'))
                processing = json.loads(proof_text(saved, 'receipt'))
                self.assertTrue(compat['passed'])
                self.assertEqual(compat['case_id'], item['case_id'])
                self.assertEqual(compat['candidate_id'], 'primary')
                self.assertEqual(compat['construction_sha256'], item['construction_sha256'])
                self.assertEqual(compat['negative_log_sha256'], negative['log_sha256'])
                self.assertTrue(processing['passed'])
                self.assertTrue(processing['recorded_only'])
                self.assertTrue(processing['originals_preserved'])
                self.assertEqual(processing['case_id'], item['case_id'])
                self.assertEqual(processing['candidate_id'], 'primary')
                self.assertEqual(processing['native_revision']['construction_sha256'],
                                 item['construction_sha256'])
                self.assertFalse(processing['physical_acceptance_claimed'])
                self.assertFalse(processing['legal_acceptance_claimed'])
                physical = item['physical_cpu_proof']
                self.assertEqual(physical['construction_sha256'], item['construction_sha256'])
                self.assertEqual(physical['saved_processing_receipt_sha256'],
                                 saved['receipt_sha256'])
                decoded = {}
                for name, binding in physical['fixtures'].items():
                    raw = zlib.decompress(base64.b64decode(
                        binding['payload_zlib_base64'], validate=True))
                    self.assertEqual(len(raw), binding['uncompressed_bytes'])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), binding['sha256'])
                    decoded[name] = raw
                for kind, status in expected.items():
                    self.assertEqual(physical['exit_codes'][kind], 0)
                    result = json.loads(decoded[kind + '_json'])
                    self.assertEqual(result['physical_checks']['maneuver']['status'], status)
                    self.assertFalse(result['physical_acceptance_claimed'])
                self.assertEqual(physical['exit_codes']['lifecycle'], 0)
                life = json.loads(decoded['lifecycle_json'])
                self.assertEqual(life['saved_processing_receipt_sha256'],
                                 saved['receipt_sha256'])
                self.assertTrue(life['failed_encoder_rejected'])
                self.assertTrue(life['premature_release_rejected'])

    def test_frame_48_qualified_physical_and_lifecycle_proofs(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0001')
        qualified = row['qualified_primary']
        proof = qualified['physical_cpu_proof']
        self.assertEqual(proof['case_id'], qualified['case_id'])
        self.assertEqual(proof['candidate_id'], 'primary')
        self.assertEqual(proof['construction_sha256'], qualified['construction_sha256'])
        self.assertEqual(proof['saved_processing_receipt_sha256'],
                         qualified['current_runtime_proof']['recorded_only_saved']['receipt_sha256'])
        decoded = {}
        for name, binding in proof['fixtures'].items():
            raw = zlib.decompress(base64.b64decode(
                binding['payload_zlib_base64'], validate=True))
            self.assertEqual(len(raw), binding['uncompressed_bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), binding['sha256'])
            decoded[name] = raw
        for kind, status in [('complete_motion', 'met'),
                             ('incomplete_motion', 'not_met'),
                             ('missing_evidence', 'unverified')]:
            self.assertEqual(proof['exit_codes'][kind], 0)
            result = json.loads(decoded[kind + '_json'])
            self.assertEqual(result['physical_checks']['maneuver']['status'], status)
            self.assertEqual(result['maneuver_completed'], status == 'met')
            self.assertFalse(result['physical_acceptance_claimed'])
        self.assertEqual(proof['exit_codes']['lifecycle'], 0)
        life = json.loads(decoded['lifecycle_json'])
        self.assertEqual(life['saved_processing_receipt_sha256'],
                         proof['saved_processing_receipt_sha256'])
        self.assertEqual(life['events'], ['capture_finished', 'encoders_closed',
                                          'restoration_verified', 'native_exit',
                                          'owner_released', 'saved_processing_started'])
        self.assertTrue(life['failed_encoder_rejected'])
        self.assertTrue(life['premature_release_rejected'])

    def test_frame_48_qualified_current_runtime_receipts(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0001')
        qualified = row['qualified_primary']
        proof = qualified['current_runtime_proof']
        positive = proof['positive_compatibility']
        negative = proof['negative_compatibility']
        saved = proof['recorded_only_saved']
        for receipt in (positive, saved):
            self.assertEqual(receipt['exit_code'], 0)
            for field in ('receipt', 'analysis_log'):
                payload = proof_text(receipt, field).encode()
                self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                 receipt[field + '_sha256'])
        self.assertEqual(hashlib.sha256(negative['log_payload'].encode()).hexdigest(),
                         negative['log_sha256'])
        compatibility = json.loads(proof_text(positive, 'receipt'))
        processing = json.loads(proof_text(saved, 'receipt'))
        self.assertTrue(compatibility['passed'])
        self.assertEqual(compatibility['case_id'], qualified['case_id'])
        self.assertEqual(compatibility['candidate_id'], 'primary')
        self.assertEqual(compatibility['construction_sha256'],
                         qualified['construction_sha256'])
        self.assertEqual(compatibility['negative_log_sha256'], negative['log_sha256'])
        self.assertTrue(processing['passed'])
        self.assertTrue(processing['recorded_only'])
        self.assertTrue(processing['originals_preserved'])
        self.assertEqual(processing['case_id'], qualified['case_id'])
        self.assertEqual(processing['candidate_id'], 'primary')
        self.assertEqual(processing['native_revision']['construction_sha256'],
                         qualified['construction_sha256'])
        self.assertFalse(processing['physical_acceptance_claimed'])
        self.assertFalse(processing['legal_acceptance_claimed'])

    def test_frame_40_qualified_physical_and_lifecycle_proofs(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0002')
        cases = [('primary', row['qualified_primary'])] + [
            (item['id'], item) for item in row['qualified_fallbacks']['candidates']]
        expected = {'complete_motion': 'met',
                    'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}
        for candidate, item in cases:
            with self.subTest(candidate=candidate):
                proof = item['physical_cpu_proof']
                self.assertEqual(proof['candidate_id'], candidate)
                self.assertEqual(proof['case_id'], item['case_id'])
                self.assertEqual(proof['construction_sha256'], item['construction_sha256'])
                self.assertEqual(proof['saved_processing_receipt_sha256'],
                                 item['current_runtime_proof']['recorded_only_saved']['receipt_sha256'])
                decoded = {}
                for name, binding in proof['fixtures'].items():
                    raw = zlib.decompress(base64.b64decode(
                        binding['payload_zlib_base64'], validate=True))
                    self.assertEqual(len(raw), binding['uncompressed_bytes'])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), binding['sha256'])
                    decoded[name] = raw
                for kind, status in expected.items():
                    self.assertEqual(proof['exit_codes'][kind], 0)
                    result = json.loads(decoded[kind + '_json'])
                    self.assertEqual(result['physical_checks']['maneuver']['status'], status)
                    self.assertEqual(result['maneuver_completed'], status == 'met')
                    self.assertFalse(result['physical_acceptance_claimed'])
                self.assertEqual(proof['exit_codes']['lifecycle'], 0)
                life = json.loads(decoded['lifecycle_json'])
                self.assertEqual(life['candidate_id'], candidate)
                self.assertEqual(life['saved_processing_receipt_sha256'],
                                 proof['saved_processing_receipt_sha256'])
                self.assertEqual(life['events'], ['capture_finished', 'encoders_closed',
                                                  'restoration_verified', 'native_exit',
                                                  'owner_released', 'saved_processing_started'])
                self.assertTrue(life['failed_encoder_rejected'])
                self.assertTrue(life['premature_release_rejected'])

    def test_frame_40_qualified_fallback_current_runtime_proofs(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0002')
        full = HERE.name + '__c125745-1-0002'
        items = row['qualified_fallbacks']['candidates']
        self.assertEqual([item['id'] for item in items],
                         ['fallback1', 'fallback2', 'fallback3'])
        self.assertEqual([item['changed_knobs'] for item in items],
                         [['other_release_frame'], ['site.camera_poses.overview'],
                          ['site.approaches.other.route_xy_m']])
        self.assertEqual(len({item['trigger']['metric'] for item in items}), 3)
        hashes = set()
        for item in items:
            with self.subTest(candidate=item['id']):
                payload = construction_bytes(item)
                self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                 item['construction_sha256'])
                bundle = json.loads(payload)
                config = json.loads(next(file['content'] for file in bundle['files']
                                         if file['path'] == 'config.json'))
                self.assertEqual(bundle['case_id'], full)
                self.assertEqual(config['selected_case_id'], full)
                self.assertTrue(item['changed_knobs'])
                self.assertTrue(item['trigger']['source'])
                self.assertTrue(item['trigger']['failure_condition'])
                self.assertTrue(item['trigger']['remedy'])
                offline = item['offline']
                self.assertEqual(offline['exit_code'], 0)
                self.assertFalse(offline['simulation_started'])
                for field in ('log', 'command_log'):
                    self.assertEqual(hashlib.sha256(proof_text(offline, field).encode()).hexdigest(),
                                     offline[field + '_sha256'])
                outcome = json.loads(offline['command_log_payload'])
                self.assertTrue(outcome['offline_passed'])
                self.assertEqual(outcome['candidate_id'], item['id'])
                proof = item['current_runtime_proof']
                positive = proof['positive_compatibility']
                negative = proof['negative_compatibility']
                saved = proof['recorded_only_saved']
                for receipt in (positive, saved):
                    self.assertEqual(receipt['exit_code'], 0)
                    for field in ('receipt', 'analysis_log'):
                        self.assertEqual(hashlib.sha256(proof_text(receipt, field).encode()).hexdigest(),
                                         receipt[field + '_sha256'])
                self.assertEqual(hashlib.sha256(negative['log_payload'].encode()).hexdigest(),
                                 negative['log_sha256'])
                compatibility = json.loads(proof_text(positive, 'receipt'))
                processed = json.loads(proof_text(saved, 'receipt'))
                self.assertEqual(compatibility['case_id'], full)
                self.assertEqual(compatibility['candidate_id'], item['id'])
                self.assertEqual(compatibility['construction_sha256'],
                                 item['construction_sha256'])
                self.assertEqual(compatibility['negative_log_sha256'],
                                 negative['log_sha256'])
                self.assertTrue(compatibility['passed'])
                self.assertEqual(processed['candidate_id'], item['id'])
                self.assertEqual(processed['native_revision']['construction_sha256'],
                                 item['construction_sha256'])
                self.assertTrue(processed['passed'])
                self.assertTrue(processed['recorded_only'])
                self.assertTrue(processed['originals_preserved'])
                self.assertFalse(processed['physical_acceptance_claimed'])
                self.assertFalse(processed['legal_acceptance_claimed'])
                hashes.add(item['construction_sha256'])
        self.assertEqual(len(hashes), 3)

    def test_frame_40_qualified_current_runtime_receipts(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0002')
        qualified = row['qualified_primary']
        proof = qualified['current_runtime_proof']
        positive = proof['positive_compatibility']
        negative = proof['negative_compatibility']
        saved = proof['recorded_only_saved']
        for receipt in (positive, saved):
            self.assertEqual(receipt['exit_code'], 0)
            for field in ('receipt', 'analysis_log'):
                self.assertEqual(hashlib.sha256(proof_text(receipt, field).encode()).hexdigest(),
                                 receipt[field + '_sha256'])
        self.assertEqual(hashlib.sha256(negative['log_payload'].encode()).hexdigest(),
                         negative['log_sha256'])
        compatibility = json.loads(proof_text(positive, 'receipt'))
        processing = json.loads(proof_text(saved, 'receipt'))
        self.assertEqual(compatibility['case_id'], qualified['case_id'])
        self.assertEqual(compatibility['construction_sha256'],
                         qualified['construction_sha256'])
        self.assertEqual(compatibility['negative_log_sha256'], negative['log_sha256'])
        self.assertTrue(compatibility['passed'])
        self.assertEqual(processing['case_id'], qualified['case_id'])
        self.assertEqual(processing['native_revision']['construction_sha256'],
                         qualified['construction_sha256'])
        self.assertTrue(processing['passed'])
        self.assertTrue(processing['recorded_only'])
        self.assertTrue(processing['originals_preserved'])
        self.assertFalse(processing['physical_acceptance_claimed'])
        self.assertFalse(processing['legal_acceptance_claimed'])

    def test_remaining_timing_and_hold_points_qualified_offline(self):
        index = read('sweep-constructions/index.json')
        expected = {'c125745-1-0002': 40, 'c125745-1-0001': 48,
                    'c125745-2-0000': 0, 'c125745-2-0002': 8,
                    'c125745-2-0001': 16}
        for row in index['constructions']:
            short = row['case_id']
            if short not in expected:
                continue
            with self.subTest(case=short):
                qualified = row['qualified_primary']
                full = HERE.name + '__' + short
                payload = construction_bytes(qualified)
                self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                 qualified['construction_sha256'])
                bundle = json.loads(payload)
                config = json.loads(next(file['content'] for file in bundle['files']
                                         if file['path'] == 'config.json'))
                self.assertEqual(bundle['case_id'], full)
                self.assertEqual(config['selected_case_id'], full)
                self.assertEqual(config[row['sweep_point']['axis']], expected[short])
                offline = qualified['offline']
                self.assertEqual(offline['exit_code'], 0)
                self.assertFalse(offline['simulation_started'])
                for field in ('log', 'command_log'):
                    self.assertEqual(hashlib.sha256(proof_text(offline, field).encode()).hexdigest(),
                                     offline[field + '_sha256'])
                outcome = json.loads(offline['command_log_payload'])
                self.assertTrue(outcome['offline_passed'])
                self.assertFalse(outcome['simulation_started'])
                self.assertEqual(outcome['case_id'], full)

    def test_qualified_fallback_physical_classifier_payloads(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0000')
        expected = {'complete_motion': 'met',
                    'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}
        for item in row['qualified_fallbacks']['candidates']:
            proof = item['physical_cpu_proof']
            self.assertEqual(proof['candidate_id'], item['id'])
            self.assertEqual(proof['case_id'], item['case_id'])
            self.assertEqual(proof['construction_sha256'], item['construction_sha256'])
            lifecycle = proof['lifecycle']
            self.assertEqual(lifecycle['exit_code'], 0)
            for binding in lifecycle['files'].values():
                self.assertEqual(hashlib.sha256(binding['payload'].encode()).hexdigest(),
                                 binding['sha256'])
            life = json.loads(lifecycle['files']['json']['payload'])
            self.assertEqual(life['candidate_id'], item['id'])
            self.assertEqual(life['saved_processing_receipt_sha256'],
                             item['current_runtime_proof']['recorded_only_saved']['receipt_sha256'])
            self.assertEqual(life['events'], ['capture_finished', 'encoders_closed',
                                              'restoration_verified', 'native_exit',
                                              'owner_released', 'saved_processing_started'])
            self.assertTrue(life['failed_encoder_rejected'])
            self.assertTrue(life['premature_release_rejected'])
            for kind, status in expected.items():
                with self.subTest(candidate=item['id'], kind=kind):
                    self.assertEqual(proof['exit_codes'][kind], 0)
                    for suffix in ('json', 'log'):
                        binding = proof['fixtures'][kind + '_' + suffix]
                        self.assertEqual(hashlib.sha256(binding['payload'].encode()).hexdigest(),
                                         binding['sha256'])
                    result = json.loads(proof['fixtures'][kind + '_json']['payload'])
                    self.assertEqual(result['physical_checks']['maneuver']['status'], status)
                    self.assertEqual(result['maneuver_completed'], status == 'met')
                    self.assertFalse(result['physical_acceptance_claimed'])

    def test_qualified_primary_physical_classifier_payloads(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0000')
        qualified = row['qualified_primary']
        proof = qualified['physical_cpu_proof']
        self.assertEqual(proof['case_id'], qualified['case_id'])
        self.assertEqual(proof['construction_sha256'], qualified['construction_sha256'])
        lifecycle = proof['lifecycle']
        self.assertEqual(lifecycle['exit_code'], 0)
        for binding in lifecycle['files'].values():
            self.assertEqual(hashlib.sha256(binding['payload'].encode()).hexdigest(),
                             binding['sha256'])
        life = json.loads(lifecycle['files']['json']['payload'])
        self.assertEqual(life['candidate_id'], 'primary')
        self.assertEqual(life['saved_processing_receipt_sha256'],
                         qualified['current_runtime_proof']['recorded_only_saved']['receipt_sha256'])
        self.assertEqual(life['events'], ['capture_finished', 'encoders_closed',
                                          'restoration_verified', 'native_exit',
                                          'owner_released', 'saved_processing_started'])
        self.assertTrue(life['failed_encoder_rejected'])
        self.assertTrue(life['premature_release_rejected'])
        expected = {'complete_motion': 'met',
                    'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}
        for kind, status in expected.items():
            with self.subTest(kind=kind):
                self.assertEqual(proof['exit_codes'][kind], 0)
                for suffix in ('json', 'log'):
                    binding = proof['fixtures'][kind + '_' + suffix]
                    self.assertEqual(hashlib.sha256(binding['payload'].encode()).hexdigest(),
                                     binding['sha256'])
                result = json.loads(proof['fixtures'][kind + '_json']['payload'])
                self.assertEqual(result['physical_checks']['maneuver']['status'], status)
                self.assertEqual(result['maneuver_completed'], status == 'met')
                self.assertFalse(result['physical_acceptance_claimed'])

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
                payload = construction_bytes(item)
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
                proof = item['current_runtime_proof']
                positive = proof['positive_compatibility']
                negative = proof['negative_compatibility']
                saved = proof['recorded_only_saved']
                for binding in (positive, saved):
                    self.assertEqual(hashlib.sha256(proof_text(binding, 'receipt').encode()).hexdigest(),
                                     binding['receipt_sha256'])
                    self.assertEqual(hashlib.sha256(binding['analysis_log_payload'].encode()).hexdigest(),
                                     binding['analysis_log_sha256'])
                    self.assertEqual(binding['exit_code'], 0)
                self.assertEqual(hashlib.sha256(negative['log_payload'].encode()).hexdigest(),
                                 negative['log_sha256'])
                receipt = json.loads(proof_text(positive, 'receipt'))
                processed = json.loads(proof_text(saved, 'receipt'))
                self.assertEqual(receipt['case_id'], full_id)
                self.assertEqual(receipt['candidate_id'], item['id'])
                self.assertEqual(receipt['construction_sha256'], item['construction_sha256'])
                self.assertEqual(receipt['negative_log_sha256'], negative['log_sha256'])
                self.assertTrue(receipt['passed'])
                self.assertEqual(processed['candidate_id'], item['id'])
                self.assertEqual(processed['native_revision']['construction_sha256'],
                                 item['construction_sha256'])
                self.assertTrue(processed['recorded_only'])
                self.assertTrue(processed['passed'])
                self.assertFalse(processed['physical_acceptance_claimed'])
                hashes.add(item['construction_sha256'])
        self.assertEqual(len(hashes), 3)

    def test_first_qualified_primary_current_runtime_receipts(self):
        index = read('sweep-constructions/index.json')
        row = next(item for item in index['constructions']
                   if item['case_id'] == 'c125745-1-0000')
        qualified = row['qualified_primary']
        proof = qualified['current_runtime_proof']
        check = lambda payload, expected: self.assertEqual(
            hashlib.sha256(payload.encode()).hexdigest(), expected)
        positive = proof['positive_compatibility']
        negative = proof['negative_compatibility']
        saved = proof['recorded_only_saved']
        check(proof_text(positive, 'receipt'), positive['receipt_sha256'])
        check(positive['analysis_log_payload'], positive['analysis_log_sha256'])
        check(negative['log_payload'], negative['log_sha256'])
        check(proof_text(saved, 'receipt'), saved['receipt_sha256'])
        check(saved['analysis_log_payload'], saved['analysis_log_sha256'])
        compatibility = json.loads(proof_text(positive, 'receipt'))
        processed = json.loads(proof_text(saved, 'receipt'))
        for receipt in (compatibility, processed):
            self.assertEqual(receipt['case_id'], qualified['case_id'])
        self.assertEqual(compatibility['construction_sha256'],
                         qualified['construction_sha256'])
        self.assertEqual(compatibility['negative_log_sha256'],
                         negative['log_sha256'])
        self.assertTrue(compatibility['passed'])
        self.assertTrue(processed['passed'])
        self.assertTrue(processed['recorded_only'])
        self.assertFalse(processed['physical_acceptance_claimed'])
        self.assertFalse(processed['legal_acceptance_claimed'])
        self.assertEqual(processed['native_revision']['construction_sha256'],
                         qualified['construction_sha256'])

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
                primary_bytes = historical_bytes(row)
                primary = json.loads(primary_bytes)
                self.assertEqual(hashlib.sha256(primary_bytes).hexdigest(), row['sha256'])
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
                    fallback_bytes = historical_bytes(fallback)
                    self.assertEqual(hashlib.sha256(fallback_bytes).hexdigest(),
                                     fallback['construction_sha256'])
                    constructions.add(fallback['construction_sha256'])
                    alternate = json.loads(fallback_bytes)
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
            archive_id = 'fallback2' if candidate_id == 'fallback3' else candidate_id
            archive_path = root / '_shared' / f'c125745-sweep-{archive_id}-proofs-2026-11-23.json'
            archive = json.loads(source_bytes(archive_path))
            if candidate_id == 'fallback3':
                nested = archive['fallback3_archive']
                self.assertEqual(nested['source_filename'],
                                 'c125745-sweep-fallback3-proofs-2026-11-23.json')
                archive = nested['payload']
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

    def test_frame32_fallback3_current_physical_diagnostics(self):
        plan = read('case-plan.json')['frame32_fallback3_physical_cpu_diagnostics']
        manifest = read('execution-manifest.json')
        case = next(item for item in manifest['cases'] if item['case_id'] == plan['case_id'])
        candidate = next(item for item in case['candidates'] if item['id'] == 'fallback3')
        self.assertEqual(plan['construction_sha256'], candidate['construction_sha256'])
        self.assertEqual(plan['script_sha256'], digest('physical_motion_fixture.py'))
        self.assertEqual(plan['saved_receipt_sha256'],
                         digest(candidate['post_capture']['test_log']))
        self.assertEqual(plan['compatibility_receipt_sha256'],
                         digest(candidate['compatibility']['receipt']))
        for kind, status in (('complete_motion', 'met'),
                             ('incomplete_motion', 'not_met'),
                             ('missing_evidence', 'unverified')):
            proof = plan['proofs'][kind]
            self.assertEqual(hashlib.sha256(proof['receipt_json'].encode()).hexdigest(),
                             proof['receipt_sha256'])
            receipt = json.loads(proof['receipt_json'])
            self.assertEqual(receipt['physical_checks']['maneuver']['status'], status)
            self.assertFalse(receipt['physical_acceptance_claimed'])
        lifecycle = plan['proofs']['lifecycle']
        self.assertEqual(hashlib.sha256(lifecycle['receipt_json'].encode()).hexdigest(),
                         lifecycle['receipt_sha256'])
        receipt = json.loads(lifecycle['receipt_json'])
        self.assertEqual(receipt['saved_processing_receipt_sha256'],
                         plan['saved_receipt_sha256'])
        self.assertTrue(receipt['failed_encoder_rejected'])
        self.assertTrue(receipt['premature_release_rejected'])
        negative = plan['negative_binding_check']
        self.assertNotEqual(negative['exit_code'], 0)
        self.assertIn(negative['error_contains'], negative['log_text'])
        self.assertEqual(hashlib.sha256(negative['log_text'].encode()).hexdigest(),
                         negative['log_sha256'])

    def test_frame40_fallback1_current_physical_diagnostics(self):
        plan = read('case-plan.json')['frame40_fallback1_physical_cpu_diagnostics']
        manifest = read('execution-manifest.json')
        case = next(item for item in manifest['cases'] if item['case_id'] == plan['case_id'])
        candidate = next(item for item in case['candidates'] if item['id'] == 'fallback1')
        self.assertEqual(plan['construction_sha256'], candidate['construction_sha256'])
        self.assertEqual(plan['saved_receipt_sha256'],
                         digest(candidate['post_capture']['test_log']))
        self.assertEqual(plan['compatibility_receipt_sha256'],
                         digest(candidate['compatibility']['receipt']))
        for kind, status in (('complete_motion', 'met'),
                             ('incomplete_motion', 'not_met'),
                             ('missing_evidence', 'unverified')):
            proof = plan['proofs'][kind]
            self.assertEqual(hashlib.sha256(proof['receipt_json'].encode()).hexdigest(),
                             proof['receipt_sha256'])
            receipt = json.loads(proof['receipt_json'])
            self.assertEqual(receipt['physical_checks']['maneuver']['status'], status)
            self.assertFalse(receipt['physical_acceptance_claimed'])
        life = json.loads(plan['proofs']['lifecycle']['receipt_json'])
        self.assertEqual(life['saved_processing_receipt_sha256'],
                         plan['saved_receipt_sha256'])
        self.assertTrue(life['failed_encoder_rejected'])
        self.assertTrue(life['premature_release_rejected'])
        negative = plan['negative_binding_check']
        self.assertIn(negative['error_contains'], negative['log_text'])

    def test_frame40_fallback23_retained_current_cpu_receipts(self):
        plan = read('case-plan.json')
        manifest = read('execution-manifest.json')
        for candidate_id in ('fallback2', 'fallback3'):
            with self.subTest(candidate=candidate_id):
                proof = plan[f'frame40_{candidate_id}_current_cpu_proof']
                case = next(item for item in manifest['cases']
                            if item['case_id'] == proof['case_id'])
                expected_attempt = {
                    'fallback2': '730d0153a4eabc6fa89afd21393ee1f1ffd8dd2653763503a2b72b914c91c573',
                    'fallback3': 'b4643eefe440c28408bbd2cf5f0841f0615eb7fbd5006ff73ee6aa3cc7bf4977',
                }
                self.assertEqual(proof['execution_manifest_file_sha256_at_attempt'],
                                 expected_attempt[candidate_id])
                candidate = next(item for item in case['candidates']
                                 if item['id'] == candidate_id)
                self.assertEqual(proof['construction_sha256'],
                                 candidate['construction_sha256'])
                self.assertEqual(proof['bound_execution_manifest_file_sha256'],
                                 {'fallback2': expected_attempt['fallback3'],
                                  'fallback3': 'fbe11390c4880a90bd670154f49721177b67d1b4466952da8775466eb328d2c2'}[candidate_id])
                self.assertEqual(candidate['compatibility']['sha256'],
                                 proof['artifacts']['compatibility.json']['sha256'])
                self.assertEqual(digest(candidate['post_capture']['test_log']),
                                 proof['artifacts']['processing.json']['sha256'])
                decoded = {}
                for name, item in proof['artifacts'].items():
                    data = zlib.decompress(base64.b64decode(
                        item['payload'], validate=True))
                    self.assertEqual(len(data), item['byte_length'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(),
                                     item['sha256'])
                    decoded[name] = data
                receipt = json.loads(decoded['compatibility.json'])
                saved = json.loads(decoded['processing.json'])
                self.assertTrue(receipt['passed'])
                self.assertEqual(receipt['candidate_id'], candidate_id)
                self.assertEqual(receipt['negative_log_sha256'],
                                 proof['artifacts']['negative-analysis.log']['sha256'])
                self.assertEqual(saved['native_revision']['construction_sha256'],
                                 candidate['construction_sha256'])
                self.assertTrue(saved['passed'])
                self.assertTrue(saved['recorded_only'])
                self.assertTrue(saved['originals_preserved'])
                self.assertEqual(saved['timestamp_joins']['frames'], 135)

    def test_frame40_fallback2_current_physical_diagnostics(self):
        plan = read('case-plan.json')['frame40_fallback2_physical_cpu_diagnostics']
        manifest = read('execution-manifest.json')
        case = next(item for item in manifest['cases']
                    if item['case_id'] == plan['case_id'])
        candidate = next(item for item in case['candidates']
                         if item['id'] == 'fallback2')
        self.assertEqual(plan['manifest_sha256'],
                         'b4643eefe440c28408bbd2cf5f0841f0615eb7fbd5006ff73ee6aa3cc7bf4977')
        self.assertEqual(plan['construction_sha256'], candidate['construction_sha256'])
        self.assertEqual(plan['script_sha256'], digest('physical_motion_fixture.py'))
        self.assertEqual(plan['saved_receipt_sha256'],
                         digest(candidate['post_capture']['test_log']))
        for kind, status in (('complete_motion', 'met'),
                             ('incomplete_motion', 'not_met'),
                             ('missing_evidence', 'unverified')):
            proof = plan['proofs'][kind]
            self.assertEqual(hashlib.sha256(proof['receipt_json'].encode()).hexdigest(),
                             proof['receipt_sha256'])
            receipt = json.loads(proof['receipt_json'])
            self.assertEqual(receipt['physical_checks']['maneuver']['status'], status)
            self.assertFalse(receipt['physical_acceptance_claimed'])
        life = json.loads(plan['proofs']['lifecycle']['receipt_json'])
        self.assertEqual(life['saved_processing_receipt_sha256'],
                         plan['saved_receipt_sha256'])
        self.assertTrue(life['failed_encoder_rejected'])
        self.assertTrue(life['premature_release_rejected'])
        negative = plan['negative_binding_check']
        self.assertNotEqual(negative['exit_code'], 0)
        self.assertIn(negative['error_contains'], negative['log_text'])

    def test_frame40_fallback3_current_physical_diagnostics(self):
        plan = read('case-plan.json')['frame40_fallback3_physical_cpu_diagnostics']
        manifest = read('execution-manifest.json')
        case = next(item for item in manifest['cases']
                    if item['case_id'] == plan['case_id'])
        candidate = next(item for item in case['candidates']
                         if item['id'] == 'fallback3')
        self.assertEqual(plan['manifest_sha256'],
                         'fbe11390c4880a90bd670154f49721177b67d1b4466952da8775466eb328d2c2')
        self.assertEqual(plan['construction_sha256'], candidate['construction_sha256'])
        self.assertEqual(plan['script_sha256'], digest('physical_motion_fixture.py'))
        self.assertEqual(plan['compatibility_receipt_sha256'],
                         digest(candidate['compatibility']['receipt']))
        self.assertEqual(plan['saved_receipt_sha256'],
                         digest(candidate['post_capture']['test_log']))
        for kind, status in (('complete_motion', 'met'),
                             ('incomplete_motion', 'not_met'),
                             ('missing_evidence', 'unverified')):
            proof = plan['proofs'][kind]
            self.assertEqual(hashlib.sha256(proof['receipt_json'].encode()).hexdigest(),
                             proof['receipt_sha256'])
            receipt = json.loads(proof['receipt_json'])
            self.assertEqual(receipt['physical_checks']['maneuver']['status'], status)
            self.assertFalse(receipt['physical_acceptance_claimed'])
        life = json.loads(plan['proofs']['lifecycle']['receipt_json'])
        self.assertEqual(life['saved_processing_receipt_sha256'],
                         plan['saved_receipt_sha256'])
        self.assertTrue(life['failed_encoder_rejected'])
        self.assertTrue(life['premature_release_rejected'])
        negative = plan['negative_binding_check']
        self.assertNotEqual(negative['exit_code'], 0)
        self.assertEqual(hashlib.sha256(negative['log_text'].encode()).hexdigest(),
                         negative['log_sha256'])
        self.assertIn(negative['error_contains'], negative['log_text'])

    def test_frame24_fallbacks_retained_current_cpu_receipts(self):
        manifest = read('execution-manifest.json')
        for n in (1, 2, 3):
            plan = read('case-plan.json')[f'frame24_fallback{n}_current_cpu_proof']
            case = next(item for item in manifest['cases']
                        if item['case_id'] == plan['case_id'])
            candidate = next(item for item in case['candidates']
                             if item['id'] == plan['candidate_id'])
            self.assertEqual(plan['attempt_manifest_sha256'],
                             'fbe11390c4880a90bd670154f49721177b67d1b4466952da8775466eb328d2c2')
            self.assertEqual(plan['bound_manifest_sha256'], digest('execution-manifest.json'))
            self.assertEqual(plan['receipts']['compatibility_sha256'],
                             digest(candidate['compatibility']['receipt']))
            self.assertEqual(plan['receipts']['negative_sha256'],
                             digest(candidate['compatibility']['negative_log']))
            self.assertEqual(plan['receipts']['saved_sha256'],
                             digest(candidate['post_capture']['test_log']))
            self.assertEqual(plan['construction_sha256'], candidate['construction_sha256'])
            receipts = plan['receipts']
            for name in ('compatibility', 'negative', 'saved'):
                payload = zlib.decompress(base64.b64decode(
                    receipts[name + '_zlib_base64'], validate=True))
                self.assertEqual(len(payload), receipts[name + '_bytes'])
                self.assertEqual(hashlib.sha256(payload).hexdigest(),
                                 receipts[name + '_sha256'])
                if name == 'negative':
                    self.assertIn(plan['negative_error_contains'], payload.decode())
                    continue
                receipt = json.loads(payload)
                self.assertTrue(receipt['passed'])
                self.assertEqual(receipt['case_id'], plan['case_id'])
                self.assertEqual(receipt['candidate_id'], plan['candidate_id'])
                if name == 'saved':
                    self.assertTrue(receipt['recorded_only'])
                    self.assertFalse(receipt['missing_evidence'])
                    self.assertEqual(receipt['native_revision']['construction_sha256'],
                                     plan['construction_sha256'])
