"""CARLA-free source gate and exact-case tests for the law contrast."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from governing_law_runner import source_packet, request
from finalize_governing_law import law_source

REPO = Path(__file__).resolve().parents[3]
ASSIGNMENT = 'training__C229977__NRS-484B-450-1a__motor_vehicle_driver'


class GoverningLawTests(unittest.TestCase):
    def test_both_exact_requests_hold_sidewalk_target(self):
        for state in ('absent', 'present'):
            value = request(160, ASSIGNMENT + '__governing_law_' + state)
            self.assertTrue(value['requested_sidewalk_occupancy'])
            self.assertEqual(value['target_lateral_m'], -5.0)
        with self.assertRaises(ValueError):
            request(160, ASSIGNMENT + '__probe_2')

    def test_absent_packet_has_no_binding(self):
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as tmp:
            root = Path(tmp)
            case = ASSIGNMENT + '__governing_law_absent'
            packet = source_packet(root, case)
            result = law_source(root, {'case_id': case},
                                {'governing_law_presence_requested': False,
                                 'governing_law_packet_source': 'law-authority.json'})
            self.assertIsNone(packet['authority_binding'])
            self.assertFalse(result['law_authority_independently_verified'])

    def test_present_requires_separate_source_and_rejects_tamper(self):
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as tmp:
            root = Path(tmp)
            case = ASSIGNMENT + '__governing_law_present'
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'requires a separate'):
                    source_packet(root, case)
            candidate = root / 'candidate.txt'
            candidate.write_text('Diagnostic source shape only; authorization is unreviewed.\n')
            with patch.dict(os.environ, {'C229977_GOVERNING_LAW_SOURCE': str(candidate),
                                         'C229977_GOVERNING_LAW_CITATION': 'diagnostic-only'}):
                packet = source_packet(root, case)
            context = {'governing_law_presence_requested': True,
                       'governing_law_packet_source': 'law-authority.json'}
            result = law_source(root, {'case_id': case}, context)
            self.assertEqual(result['law_text_source_sha256'], hashlib.sha256((root / 'specific-law.txt').read_bytes()).hexdigest())
            self.assertFalse(result['law_authority_independently_verified'])
            (root / 'specific-law.txt').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                law_source(root, {'case_id': case}, context)

    def test_circular_citation_rejected(self):
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as tmp:
            root = Path(tmp)
            candidate = root / 'candidate.txt'
            candidate.write_text('Diagnostic source shape.\n')
            with patch.dict(os.environ, {'C229977_GOVERNING_LAW_SOURCE': str(candidate),
                                         'C229977_GOVERNING_LAW_CITATION': 'NRS-484B-450-1a'}):
                with self.assertRaisesRegex(ValueError, 'Circular'):
                    source_packet(root, ASSIGNMENT + '__governing_law_present')


if __name__ == '__main__':
    unittest.main()
