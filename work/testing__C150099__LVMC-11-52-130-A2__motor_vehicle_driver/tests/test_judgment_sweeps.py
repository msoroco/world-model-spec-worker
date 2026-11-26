"""Diagnostic software proofs; no City source or legal result is asserted."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from judgment_sweeps import (CONFLICT_POINTS, DESIGNATION_POINTS,
                             measure_original, preflight)
from source_packet import EXCEPTION_SOURCES, SOURCES


class JudgmentSweepTests(unittest.TestCase):
    def packet(self, root, suffix):
        case_id = ROOT.name + '__' + suffix
        site = {'cell_id': 'C150099', 'layout': 'one_way_road',
                'property_kind': 'public', 'sign_support': 'spawned_prop',
                'sign_text': 'FIRE LANE', 'posted_interval_m': [10, 30],
                'curb_y_m': 2, 'approach_waypoints': [[0, 0], [40, 0]],
                'conflict_actor_waypoints': [[3, 0], [38, 0]]}
        sources = {}
        names = list(SOURCES)
        if suffix == 'traffic_conflict_exception':
            names.append(EXCEPTION_SOURCES['lawful_traffic_conflict'])
        for name in names:
            source = root / (name + '.txt')
            source.write_text('DIAGNOSTIC ONLY ' + name + '\n')
            sources[name] = {'path': source.name,
                             'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
            if name in ('fire_code_designation', 'posting_authority', 'jurisdiction'):
                sources[name].update(reviewer='diagnostic', citation='diagnostic')
        packet = {'case_id': case_id, 'source_kind': 'reviewed_original_site',
                  'reviewer': 'diagnostic', 'site': site, 'sources': sources,
                  'sign_prop_provenance': 'diagnostic'}
        path = root / 'site.json'
        path.write_text(json.dumps(packet) + '\n')
        return path, packet

    def test_designation_points_and_missing_review(self):
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path, packet = self.packet(Path(directory), 'outside_posted_extent')
            for point in DESIGNATION_POINTS:
                result = preflight(path, packet['case_id'], point, 4.0)
                self.assertEqual(result['legal_judgment'], None)
                self.assertEqual(result['reviewed_posted_interval_m'], [10, 30])
            packet['sources']['fire_code_designation'].pop('reviewer')
            path.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'official source review missing'):
                preflight(path, packet['case_id'], DESIGNATION_POINTS[0], 4.0)

    def test_conflict_points_and_missing_source(self):
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path, packet = self.packet(Path(directory), 'traffic_conflict_exception')
            for point in CONFLICT_POINTS:
                result = preflight(path, packet['case_id'], point, 4.0)
                self.assertEqual(result['requested_actor_gap_m'], point.requested_gap_m)
                self.assertIsNone(result['legal_judgment'])
            packet['sources'].pop('traffic_conflict_source')
            path.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'original source missing'):
                preflight(path, packet['case_id'], CONFLICT_POINTS[0], 4.0)

    def test_measure_original_and_negative(self):
        rows = [{'original_frame': i, 'body_west_x_m': 29+i*.1,
                 'body_east_x_m': 33+i*.1, 'reviewed_posted_end_x_m': 30,
                 'posted_extent_sha256': 'a'*64, 'actual_actor_body_gap_m': 5+i,
                 'traffic_conflict_source_sha256': 'b'*64} for i in range(3)]
        self.assertEqual(len(measure_original(rows, DESIGNATION_POINTS[0])['measured_offset_m']), 3)
        self.assertEqual(len(measure_original(rows, CONFLICT_POINTS[0])['measured_gap_m']), 3)
        rows[1]['traffic_conflict_source_sha256'] = None
        with self.assertRaisesRegex(ValueError, 'original conflict source missing'):
            measure_original(rows, CONFLICT_POINTS[0])
        rows[1]['original_frame'] = 7
        with self.assertRaisesRegex(ValueError, 'contiguous original'):
            measure_original(rows, DESIGNATION_POINTS[0])


if __name__ == '__main__':
    unittest.main()
