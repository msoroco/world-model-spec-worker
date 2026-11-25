import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from saved_pair import audit_saved_pair
import test_saved_turn


class SavedPairTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_saved_turn.SavedTurnTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tmp.cleanup)

    def pair(self):
        fixture = self.fixture
        left = fixture.save_json('left_manifest', fixture.manifest)
        rows = json.loads((fixture.root / 'telemetry.json').read_text())
        rows[1]['ego_in_intersection'] = True
        rows[1]['pedestrian_xy'] = [1, 1]
        rows[2]['ego_in_intersection'] = True
        right_manifest = {**fixture.manifest, 'case_suffix': 'continue_pedestrian',
                          'telemetry': fixture.save_json('right_telemetry', rows)}
        right = fixture.save_json('right_manifest', right_manifest)
        return left, right

    def test_exact_source_replay_and_reuse_rejection(self):
        left, right = self.pair()
        result = audit_saved_pair('pedestrian_yield', self.fixture.root, left,
                                  self.fixture.root, right, expected_frames=3, diagnostic=True)
        self.assertEqual(result['format'], 'c111610-source-bound-red-arrow-comparison-v1')
        self.assertEqual(result['decoded_view_frames'], 24)
        self.assertFalse(result['physical_acceptance'])
        self.assertNotEqual(result['source_hashes']['left']['telemetry'],
                            result['source_hashes']['right']['telemetry'])
        with self.assertRaisesRegex(ValueError, 'same original attempt reused'):
            audit_saved_pair('pedestrian_yield', self.fixture.root, left,
                             self.fixture.root, left, expected_frames=3, diagnostic=True)

    def test_tampered_source_and_missing_difference_rejected(self):
        left, right = self.pair()
        path = self.fixture.root / 'right_telemetry.json'
        original = path.read_bytes()
        path.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            audit_saved_pair('pedestrian_yield', self.fixture.root, left,
                             self.fixture.root, right, expected_frames=3, diagnostic=True)
        path.write_bytes(original)
        rows = json.loads(path.read_text())
        rows[1]['ego_in_intersection'] = False
        right_manifest = {**self.fixture.manifest, 'case_suffix': 'continue_pedestrian',
                          'telemetry': self.fixture.save_json('right_telemetry', rows)}
        right = self.fixture.save_json('right_manifest', right_manifest)
        with self.assertRaisesRegex(ValueError, 'pedestrian precedence difference not observed'):
            audit_saved_pair('pedestrian_yield', self.fixture.root, left,
                             self.fixture.root, right, expected_frames=3, diagnostic=True)
