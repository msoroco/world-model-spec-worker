import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from source_packet import SOURCES, validate_packet


class SourcePacketTests(unittest.TestCase):
    def packet(self, root, suffix='public_park_attended'):
        case_id = ROOT.name + '__' + suffix
        site = {
            'cell_id': 'C150099', 'layout': 'one_way_road',
            'property_kind': 'public', 'sign_support': 'spawned_prop',
            'sign_text': 'FIRE LANE', 'posted_interval_m': [10, 30],
            'curb_y_m': 2, 'approach_waypoints': [[0, 0], [20, 0]],
        }
        sources = {}
        for name in SOURCES:
            source = root / (name + '.txt')
            source.write_text('diagnostic ' + name + '\n', encoding='utf-8')
            sources[name] = {'path': source.name,
                             'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
            if name in ('fire_code_designation', 'posting_authority', 'jurisdiction'):
                sources[name].update(reviewer='diagnostic reviewer', citation='diagnostic source')
        packet = {'case_id': case_id, 'source_kind': 'reviewed_original_site',
                  'reviewer': 'diagnostic reviewer', 'site': site,
                  'sources': sources, 'sign_prop_provenance': 'diagnostic prop'}
        path = root / 'site.json'
        path.write_text(json.dumps(packet) + '\n', encoding='utf-8')
        return path, packet

    def test_source_binding_and_tamper(self):
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path, packet = self.packet(Path(directory))
            site = validate_packet(path, packet['case_id'])
            self.assertEqual(site['fire_code_designation_sha256'],
                             packet['sources']['fire_code_designation']['sha256'])
            (Path(directory) / 'fire_code_designation.txt').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                validate_packet(path, packet['case_id'])

    def test_missing_official_review_and_case_rejected(self):
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path, packet = self.packet(Path(directory))
            packet['sources']['posting_authority'].pop('citation')
            path.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'official source review missing'):
                validate_packet(path, packet['case_id'])
            with self.assertRaisesRegex(ValueError, 'case identity mismatch'):
                validate_packet(path, ROOT.name + '__public_stop')

    def test_exception_has_distinct_source(self):
        scratch = WORKSPACE / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path, packet = self.packet(Path(directory), 'police_direction_exception')
            with self.assertRaisesRegex(ValueError, 'police_direction_source'):
                validate_packet(path, packet['case_id'])


if __name__ == '__main__':
    unittest.main()
