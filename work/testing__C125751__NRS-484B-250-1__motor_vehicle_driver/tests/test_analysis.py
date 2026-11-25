import hashlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path[:0] = [str(ROOT), str(REPO / 'runtime' / 'scenario_pipeline')]
from analysis import build_report, saved_result
from test_signal_crossing import MAP, REVIEW, packet, sealed_history


def write_attempt(root):
    seal, payload = sealed_history()
    history = json.loads(payload)
    files = {'signal-packet.json': json.dumps(seal).encode(),
             'signal-history.json': payload, 'review.json': REVIEW,
             'map.xodr': MAP,
             'source-packet.json': json.dumps(packet()).encode(),
             'reviewed-packet.json': json.dumps(packet()).encode(),
             'acquisition-provenance.json': json.dumps({
                 'provenance_kind': 'synthetic_fixture',
                 'diagnostic_fixture': True,
                 'review_sha256': hashlib.sha256(REVIEW).hexdigest()}).encode()}
    trace = ''.join(json.dumps({'frame': 100+i, 'time_s': row['time_s'],
                                'position': {'x': row['ego']['xy_m'][0],
                                             'y': row['ego']['xy_m'][1], 'z': 0.0},
                                'heading_deg': 0.0, 'speed_mps': 2.0})+'\n'
                    for i, row in enumerate(history['frames']))
    mapping = ''.join(json.dumps({'video_frame': i, 'carla_frame': 100+i,
                                  'time_s': row['time_s']})+'\n'
                      for i, row in enumerate(history['frames']))
    files.update({'trace.jsonl': trace.encode(),
                  'video_frames.jsonl': mapping.encode()})
    for name, content in files.items():
        (root / name).write_bytes(content)
    (root / 'acquisition.json').write_text(json.dumps({name: {
        'kind': 'original_native', 'sha256': hashlib.sha256(content).hexdigest()}
        for name, content in files.items()}))
    (root / 'config.json').write_text(json.dumps({
        'selected_case_id': 'case-1',
        'case': {'other_first': True, 'ego_light_request': 'Green'}}))
    (root / 'construction.json').write_text(json.dumps({
        'recording_description': {'channels': [
            {'name': 'ego_body_history', 'unit': 'structured record'},
            {'name': 'other_body_history', 'unit': 'structured record'}]}}))


class AnalysisTest(unittest.TestCase):
    def test_saved_finalizer_and_missing_source(self):
        scratch = REPO / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            write_attempt(root)
            report = build_report(root)
            result = saved_result(root, report)
            self.assertTrue(result['target_checks'][0]['matched'])
            self.assertEqual(result['physical_checks']['maneuver']['status'], 'met')
            self.assertEqual(result['realized_observables']['ego_entry_frame']['value'],
                             report['measurements']['signal_crossing']['value']['ego_entry_frame'])
            self.assertEqual(result['realized_observables']['other_entry_frame']['value'], 1)
            self.assertTrue((root / 'channels' / 'ego_body_history.jsonl').is_file())
            (root / 'review.json').write_bytes(REVIEW + b' ')
            with self.assertRaisesRegex(ValueError, 'stale original'):
                build_report(root)

    def test_original_time_join_rejection(self):
        scratch = REPO / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            write_attempt(root)
            path = root / 'video_frames.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[3]['time_s'] += .01
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            inventory = json.loads((root / 'acquisition.json').read_text())
            inventory['video_frames.jsonl']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            (root / 'acquisition.json').write_text(json.dumps(inventory))
            with self.assertRaisesRegex(ValueError, 'time join differs'):
                build_report(root)

    def test_byte_identical_source_symlink_rejected(self):
        scratch = REPO / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            write_attempt(root)
            source = root / 'signal-history.json'
            alias = root / 'alias-signal-history.json'
            alias.write_bytes(source.read_bytes())
            source.unlink()
            source.symlink_to(alias.name)
            with self.assertRaisesRegex(ValueError, 'Missing required source: signal-history.json'):
                build_report(root)

    def test_provenance_binding_rejects_tamper(self):
        scratch = REPO / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            write_attempt(root)
            provenance = root / 'acquisition-provenance.json'
            record = json.loads(provenance.read_text())
            record['diagnostic_fixture'] = False
            provenance.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'stale original'):
                build_report(root)
            inventory = json.loads((root / 'acquisition.json').read_text())
            inventory[provenance.name]['sha256'] = hashlib.sha256(provenance.read_bytes()).hexdigest()
            (root / 'acquisition.json').write_text(json.dumps(inventory))
            record['review_sha256'] = '0' * 64
            provenance.write_text(json.dumps(record))
            inventory[provenance.name]['sha256'] = hashlib.sha256(provenance.read_bytes()).hexdigest()
            (root / 'acquisition.json').write_text(json.dumps(inventory))
            with self.assertRaisesRegex(ValueError, 'provenance differs'):
                build_report(root)

    def test_live_signal_target_failure_is_not_hidden_by_entry_order(self):
        scratch = REPO / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            write_attempt(root)
            history_path = root / 'signal-history.json'
            history = json.loads(history_path.read_text())
            history['frames'][0]['ego_light_readback'] = 'Red'
            history_path.write_text(json.dumps(history))
            packet_path = root / 'signal-packet.json'
            packet_value = json.loads(packet_path.read_text())
            packet_value['payload_sha256'] = hashlib.sha256(history_path.read_bytes()).hexdigest()
            packet_path.write_text(json.dumps(packet_value))
            inventory_path = root / 'acquisition.json'
            inventory = json.loads(inventory_path.read_text())
            for name in ('signal-history.json', 'signal-packet.json'):
                inventory[name]['sha256'] = hashlib.sha256((root / name).read_bytes()).hexdigest()
            inventory_path.write_text(json.dumps(inventory))
            result = saved_result(root, build_report(root))
            self.assertTrue(result['target_checks'][0]['matched'])
            self.assertFalse(result['target_checks'][1]['matched'])
            self.assertEqual(result['physical_checks']['target']['status'], 'not_met')


if __name__ == '__main__':
    unittest.main()
