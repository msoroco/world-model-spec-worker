"""Software checks for the reviewed source packet; fixture is not original evidence."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewed_site import FIELDS, validate_site, verify

CASES = validate_site.__globals__['CASES']


class ReviewedSiteTests(unittest.TestCase):
    def packet(self, folder):
        road = {'controlled_access_readback': True,
                'exit_connection_readback': True,
                'highway_road_ids': [1],
                'exit_waypoints': [[-10, 0, 0], [-3, 0, 0], [5, 0, 0]],
                'highway_approach_waypoints': [[0, -12, 0], [0, -10, 0], [0, 8, 0]],
                'exit_merge_polygon_xy': [[-2, -2], [6, -2], [6, 3], [-2, 3]]}
        site = {'source_kind': 'original_native_capture', 'reviewer': 'fixture reviewer',
                'cell_id': 'C228302', 'layout': 'road', 'maneuver': 'exit_road',
                'road': road, 'ego_blueprint': 'vehicle.ego',
                'approach_blueprint': 'vehicle.approach'}
        bindings = {}
        for role, (group, field) in FIELDS.items():
            name = role + ('.xodr' if role == 'map' else '.txt')
            path = folder / name
            path.write_text('software fixture ' + role + '\n', encoding='utf-8')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            bindings[role] = {'path': name, 'sha256': digest}
            (road if group else site)[field] = digest
        packet = {'format': 'c228302-reviewed-exit-site-v1',
                  'source_kind': 'original_native_capture',
                  'diagnostic_fixture': False, 'reviewer': 'fixture reviewer',
                  'site': site, 'source_bindings': bindings}
        target = folder / 'reviewed-site.json'
        target.write_text(json.dumps(packet) + '\n', encoding='utf-8')
        return target

    def test_binding_and_tamper_rejection(self):
        scratch = ROOT.parents[1] / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as dirname:
            root = Path(dirname)
            packet = self.packet(root)
            self.assertEqual(len(verify(packet, CASES[0])['paths']), 11)
            (root / 'route.txt').write_text('changed\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source bytes changed'):
                verify(packet, CASES[0])

    def test_diagnostic_and_path_escape_rejection(self):
        scratch = ROOT.parents[1] / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as dirname:
            packet = self.packet(Path(dirname))
            data = json.loads(packet.read_text())
            data['diagnostic_fixture'] = True
            packet.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'reviewed original'):
                verify(packet, CASES[0])
            data['diagnostic_fixture'] = False
            data['source_bindings']['route']['path'] = '../route.txt'
            packet.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'unsafe or unversioned'):
                verify(packet, CASES[0])
