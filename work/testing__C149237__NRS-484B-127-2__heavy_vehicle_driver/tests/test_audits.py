import json
import tempfile
import unittest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from delivery_audit import audit_attempt
from comparison_audit import audit_comparison
from native_packet import AID


class IndependentAuditTest(unittest.TestCase):
    def test_original_attempt_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'original attempt missing'):
                audit_attempt(root / 'absent', root / 'result.json', AID + '__gap_below_500ft')

    def test_gap_comparison_requires_fixed_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = ('gap_below_500ft', 'gap_at_500ft', 'gap_above_500ft')
            paths = {}
            for index, name in enumerate(names):
                case_id = AID + '__' + name
                path = root / (name + '.json')
                path.write_text(json.dumps({
                    'format': 'c149237-original-delivery-audit-v1',
                    'case_id': case_id, 'original_frame_count': 900,
                    'measurement': {'case_id': case_id, 'original_frame_count': 900,
                                    'legal_judgment': 'unresolved',
                                    'steady_gap_min_m': 145.0 + index * 7.5,
                                    'subject_width_min_m': 2.1,
                                    'lead_width_min_m': 2.1,
                                    'same_direction_available_lane_count_min': 1},
                    'legal_status': 'unresolved',
                    'source_sha256': {'capture-seal.json': 'a' * 64},
                    'original_context': {'road_source_sha256': 'b' * 64,
                                         'route_geometry_sha256': 'c' * 64,
                                         'weather_sha256': 'd' * 64}}
                ), encoding='utf-8')
                paths[case_id] = path
            proof = audit_comparison('500ft_space_below_at_above', paths)
            self.assertEqual(proof['comparison_proof']['ordered_gap_m'], [145.0, 152.5, 160.0])
            changed = json.loads(paths[AID + '__gap_at_500ft'].read_text())
            changed['original_context']['road_source_sha256'] = 'e' * 64
            paths[AID + '__gap_at_500ft'].write_text(json.dumps(changed), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fixed original road'):
                audit_comparison('500ft_space_below_at_above', paths)
