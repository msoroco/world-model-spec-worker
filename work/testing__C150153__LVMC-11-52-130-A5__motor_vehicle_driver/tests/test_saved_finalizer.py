"""Saved finalizer tests use diagnostic media with explicit mock decoder."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from saved_finalizer import finalize
from test_independent_delivery_audit import DeliveryAuditTests


class SavedFinalizerTests(unittest.TestCase):
    def test_recorded_only_measurement_and_source_preservation(self):
        scratch = Path('.runtime-work/c150153-saved-finalizer-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, packet, sources, _ = DeliveryAuditTests().fixture(temp)
            before = hashlib.sha256((attempt / 'history.jsonl').read_bytes()).hexdigest()
            report = finalize(attempt, packet, sources, diagnostic_fixture=True,
                              decoder=lambda path, name: 900)
            self.assertEqual(report['frame_count'], 900)
            self.assertEqual(report['observed_regions'], ['west'])
            self.assertEqual(report['observed_activities'], ['parked'])
            self.assertIsNone(report['legal_judgment'])
            self.assertEqual(hashlib.sha256((attempt / 'history.jsonl').read_bytes()).hexdigest(), before)
            with self.assertRaisesRegex(ValueError, 'original Native capture'):
                finalize(attempt, packet, sources)

    def test_changed_acquisition_during_finalization_rejects(self):
        scratch = Path('.runtime-work/c150153-saved-finalizer-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, packet, sources, seal = DeliveryAuditTests().fixture(temp)
            delivery = {'case_id': seal['case_id'], 'site_packet_sha256': seal['site_packet_sha256']}
            def changed(*args, **kwargs):
                (attempt / 'overview.mkv').write_text('changed camera\n')
                return delivery
            with patch('saved_finalizer.audit', side_effect=changed):
                with self.assertRaisesRegex(ValueError, 'changed original acquisition'):
                    finalize(attempt, packet, sources, diagnostic_fixture=True,
                             decoder=lambda path, name: 900)


if __name__ == '__main__':
    unittest.main()
