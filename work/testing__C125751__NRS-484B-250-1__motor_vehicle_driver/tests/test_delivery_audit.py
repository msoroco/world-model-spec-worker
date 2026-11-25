import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from case_protocol import ASSIGNMENT, SUFFIXES
from delivery_audit import verify_core, verify_media, verify_pixels, verify_sources


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryAuditTest(unittest.TestCase):
    def fixture(self):
        scratch = REPO / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=scratch)

    def test_diagnostic_capture_cannot_pass_production_source_gate(self):
        with self.fixture() as temporary:
            attempt = Path(temporary)
            (attempt / 'capture-seal.json').write_text(json.dumps({
                'provenance_kind': 'native', 'diagnostic_fixture': True,
                'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
                'restoration': {'restored': True}, 'sources': {}}))
            for suffix in SUFFIXES:
                with self.subTest(suffix=suffix):
                    with self.assertRaisesRegex(ValueError, 'lifecycle unverified'):
                        verify_sources(ASSIGNMENT + '__' + suffix, attempt)

    def test_byte_identical_external_symlink_cannot_be_sealed_original(self):
        with self.fixture() as temporary:
            scratch = Path(temporary)
            attempt = scratch / 'attempt'
            attempt.mkdir()
            external = scratch / 'external-construction.json'
            external.write_text('{}\n')
            (attempt / 'construction.json').symlink_to(external)
            (attempt / 'capture-seal.json').write_text(json.dumps({
                'provenance_kind': 'native', 'diagnostic_fixture': False,
                'events': ['capture_finished', 'encoders_closed',
                           'restoration_verified'],
                'restoration': {'restored': True},
                'sources': {'construction.json': digest(external)}}))
            with self.assertRaisesRegex(ValueError, 'sealed Native source missing or changed'):
                verify_sources(ASSIGNMENT + '__precedence', attempt)

    def test_decode_and_pixel_receipts_reject_stale_or_missing_observations(self):
        with self.fixture() as temporary:
            attempt = Path(temporary)
            (attempt / 'traffic_spec').mkdir()
            for name, data in (('raw.mkv', b'diagnostic fixture'),
                               ('video_frames.jsonl', b'{}\n'),
                               ('traffic_spec/trace.json', b'{"scenes":[]}')):
                (attempt / name).write_bytes(data)
            auditor = attempt / 'media-auditor.py'
            auditor.write_text('# diagnostic fixture\n')
            source = {'frames': [{'time_s': 0.0}]}
            decode = {'format': 'source-decode', 'passed': True,
                      'video_sha256': digest(attempt / 'raw.mkv'),
                      'mapping_sha256': digest(attempt / 'video_frames.jsonl'),
                      'frames': 1, 'checks': {'frame_count': 'all-decoded-frames'},
                      'auditor_sha256': digest(auditor)}
            verify_media(attempt, source, decode, auditor)
            decode['video_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'decode unverified'):
                verify_media(attempt, source, decode, auditor)
            pixels = {'format': 'worker-original-pixel-review',
                      'case_id': ASSIGNMENT + '__precedence',
                      'diagnostic_fixture': False, 'reviewer': 'fixture',
                      'video_sha256': digest(attempt / 'raw.mkv'),
                      'frame_map_sha256': digest(attempt / 'video_frames.jsonl'),
                      'core_trace_sha256': digest(attempt / 'traffic_spec/trace.json'),
                      'observations': {'ego': {'visible': True, 'frame': 0,
                                               'view': 'overview', 'description': 'fixture'}}}
            with self.assertRaisesRegex(ValueError, 'actual pixels unverified: other'):
                verify_pixels(ASSIGNMENT + '__precedence', attempt, source, pixels)
            with self.assertRaisesRegex(ValueError, 'Core trace and original frame count'):
                verify_core(attempt, source)


if __name__ == '__main__':
    unittest.main()
