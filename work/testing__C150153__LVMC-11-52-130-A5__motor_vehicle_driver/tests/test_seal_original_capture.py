"""Source/owner seal protocol tests use synthetic files and mocked decoder."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from seal_original_capture import seal
from test_independent_delivery_audit import DeliveryAuditTests, sha


class OriginalSealTests(unittest.TestCase):
    def fixture(self, root):
        attempt, site, sources, prior = DeliveryAuditTests().fixture(root)
        reviewed_dir = attempt / 'reviewed-site'
        reviewed_dir.mkdir()
        shutil.copy2(site, reviewed_dir / 'packet.json')
        shutil.copytree(sources, reviewed_dir / 'sources')
        source_hashes = dict(prior['sources'])
        source_hashes['reviewed-site/packet.json'] = sha(reviewed_dir / 'packet.json')
        for source in (reviewed_dir / 'sources').rglob('*'):
            if source.is_file():
                source_hashes[str(source.relative_to(attempt))] = sha(source)
        for name in ('construction.json', 'runner.py', 'config.json'):
            (attempt / name).write_text('synthetic materialized source\n')
        revision = {'construction_sha256': sha(attempt / 'construction.json'),
                    'runner_sha256': sha(attempt / 'runner.py')}
        acquisition = {'format': 'sidewalk-elevator-native-acquisition-seal',
                       'case_id': prior['case_id'], 'site_packet_sha256': sha(site),
                       'provenance_kind': 'native', 'diagnostic_fixture': False, 'frames': 900,
                       'capture_rate_hz': 20,
                       'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
                       'native_revision': revision, 'sources': source_hashes}
        (attempt / 'capture-seal.json').write_text(json.dumps(acquisition) + '\n')
        native_exit = {'event': 'native_exit',
                       'capture_seal_sha256': sha(attempt / 'capture-seal.json'),
                       'native_revision': revision}
        (attempt / 'native-exit.json').write_text(json.dumps(native_exit) + '\n')
        receipt = {
            'event': 'owner_released', 'operator_attested': True,
            'native_construction_sha256': sha(attempt / 'construction.json'),
            'native_exit_sha256': sha(attempt / 'native-exit.json'),
        }
        path = Path(root) / 'owner-release.json'
        path.write_text(json.dumps(receipt) + '\n')
        return attempt, site, sources, path, receipt

    def test_seal_requires_external_owner_and_unchanged_sources(self):
        scratch = Path('.runtime-work/c150153-seal-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, site, sources, path, receipt = self.fixture(temp)
            with patch('seal_original_capture.audit', return_value={'frame_count': 900}):
                self.assertEqual(seal(attempt, site, sources, path, sha(path)), {'frame_count': 900})
                stamped = json.loads((attempt / 'delivery-seal.json').read_text())
                self.assertEqual(stamped['owner_receipt_sha256'], sha(path))
                self.assertEqual(stamped['sources'], json.loads((attempt / 'capture-seal.json').read_text())['sources'])
                with self.assertRaisesRegex(ValueError, 'overwrite'):
                    seal(attempt, site, sources, path, sha(path))
            (attempt / 'delivery-seal.json').unlink()
            (attempt / 'overview.mkv').write_text('changed synthetic camera\n')
            with self.assertRaisesRegex(ValueError, 'source hashes differ'):
                seal(attempt, site, sources, path, sha(path))
            self.assertFalse((attempt / 'delivery-seal.json').exists())

    def test_owner_release_and_decoder_failure_reject(self):
        scratch = Path('.runtime-work/c150153-seal-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, site, sources, path, receipt = self.fixture(temp)
            with self.assertRaisesRegex(ValueError, 'receipt hash differs'):
                seal(attempt, site, sources, path, '0' * 64)
            with patch('seal_original_capture.audit', side_effect=ValueError('full decode failed')):
                with self.assertRaisesRegex(ValueError, 'full decode failed'):
                    seal(attempt, site, sources, path, sha(path))
            self.assertFalse((attempt / 'delivery-seal.json').exists())
            receipt['operator_attested'] = False
            path.write_text(json.dumps(receipt) + '\n')
            with self.assertRaisesRegex(ValueError, 'owner release incomplete'):
                seal(attempt, site, sources, path, sha(path))

    def test_failed_native_exit_rejected_even_with_owner_attestation(self):
        scratch = Path('.runtime-work/c150153-seal-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, site, sources, path, receipt = self.fixture(temp)
            failed = json.loads((attempt / 'native-exit.json').read_text())
            failed['native_process_exit_code'] = 1
            failed['capture_command_failed'] = True
            (attempt / 'native-exit.json').write_text(json.dumps(failed) + '\n')
            receipt['native_exit_sha256'] = sha(attempt / 'native-exit.json')
            path.write_text(json.dumps(receipt) + '\n')
            with self.assertRaisesRegex(ValueError, 'owner release incomplete'):
                seal(attempt, site, sources, path, sha(path))
            self.assertFalse((attempt / 'delivery-seal.json').exists())

    def test_pinned_runtime_owner_release_receipt_joins_delivery_seal(self):
        scratch = Path('.runtime-work/c150153-seal-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, site, sources, path, _ = self.fixture(temp)
            path.unlink()
            (attempt / 'native-exit.json').unlink()
            root = HERE.parents[1]
            env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(root / '.runtime-work/c150153-owner/pipeline'),
                       PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(root / 'runtime'))
            exit_command = [str(root / '.venv-cpu/bin/python'), '-c',
                            'from pathlib import Path; from scenario_pipeline.worker_exchange.saved_processing import record_native_exit; record_native_exit(Path(__import__("sys").argv[1]))',
                            str(attempt)]
            recorded = subprocess.run(exit_command, cwd=root, env=env, capture_output=True,
                                      text=True, timeout=60)
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            command = [str(root / '.venv-cpu/bin/python'), 'runtime.py', 'owner-released',
                       '--attempt', str(attempt), '--receipt', str(path),
                       '--acknowledge-owner-released']
            result = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                    text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            with patch('seal_original_capture.audit', return_value={'frame_count': 900}):
                proof = seal(attempt, site, sources, path, sha(path))
            self.assertEqual(proof['frame_count'], 900)
            self.assertEqual(json.loads((attempt / 'delivery-seal.json').read_text())['owner_receipt_sha256'], sha(path))


if __name__ == '__main__':
    unittest.main()
