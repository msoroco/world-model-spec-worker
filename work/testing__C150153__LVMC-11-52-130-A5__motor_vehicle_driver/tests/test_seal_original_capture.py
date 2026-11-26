"""Source/owner seal protocol tests use synthetic files and mocked decoder."""
import json
from pathlib import Path
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
        (attempt / 'capture-seal.json').unlink()
        receipt = {
            'format': 'sidewalk-elevator-native-owner-release',
            'case_id': prior['case_id'], 'site_packet_sha256': sha(site),
            'provenance_kind': 'original_native', 'owner_released': True,
            'restoration_verified': True, 'native_process_exit_code': 0,
            'encoder_exit_codes': prior['encoder_exit_codes'],
            'source_hashes': prior['sources'],
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
                stamped = json.loads((attempt / 'capture-seal.json').read_text())
                self.assertEqual(stamped['owner_receipt_sha256'], sha(path))
                self.assertEqual(stamped['sources'], receipt['source_hashes'])
                with self.assertRaisesRegex(ValueError, 'overwrite'):
                    seal(attempt, site, sources, path, sha(path))
            (attempt / 'capture-seal.json').unlink()
            (attempt / 'overview.mkv').write_text('changed synthetic camera\n')
            with self.assertRaisesRegex(ValueError, 'source hashes differ'):
                seal(attempt, site, sources, path, sha(path))
            self.assertFalse((attempt / 'capture-seal.json').exists())

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
            self.assertFalse((attempt / 'capture-seal.json').exists())
            receipt['owner_released'] = False
            path.write_text(json.dumps(receipt) + '\n')
            with self.assertRaisesRegex(ValueError, 'owner release incomplete'):
                seal(attempt, site, sources, path, sha(path))


if __name__ == '__main__':
    unittest.main()
