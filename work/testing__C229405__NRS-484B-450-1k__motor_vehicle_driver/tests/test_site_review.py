"""Original source packet and Native adapter safety tests without CARLA."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(__file__).resolve().parents[3] / '.runtime-work' / 'c229405-tests'
SCRATCH.mkdir(parents=True, exist_ok=True)


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import sys
sys.path.insert(0, str(ROOT))
from test_excavation_park import scene
from excavation_park import CASES
import site_review
import native_excavation


class PacketTests(unittest.TestCase):
    def packet(self, folder, case):
        names = ('map', 'highway', 'excavation', 'traffic', 'authority')
        sources = {}
        for name in names:
            path = folder / (name + '.json')
            content = {'map_id': 'Town05', 'opendrive_sha256': 'a' * 64} if name == 'map' else {'name': name}
            path.write_text(json.dumps(content) + '\n', encoding='utf-8')
            sources[name] = {'path': path.name,
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        data = scene(case)
        data['highway_source_sha256'] = sources['highway']['sha256']
        data['excavation_source_sha256'] = sources['excavation']['sha256']
        data['traffic_actor_source_sha256'] = sources['traffic']['sha256']
        data['exception_source_sha256'] = sources['authority']['sha256']
        packet = {'case_id': ROOT.name + '__' + case.case_id,
                  'review_status': 'reviewed_original_source',
                  'diagnostic_fixture': False, 'reviewer': 'local site reviewer',
                  'review_method': 'map and roadwork source inspection',
                  'map_id': 'Town05', 'sources': sources, 'scene': data,
                  'vehicle_blueprint_id': 'vehicle.tesla.model3',
                  'traffic_blueprint_id': 'vehicle.audi.tt',
                  'excavation_markers': [
                      {'blueprint_id': 'static.prop.trafficcone01', 'xy': [0, 0]},
                      {'blueprint_id': 'static.prop.trafficcone01', 'xy': [2, 1]}],
                  'excavation_source_review': 'independent_original_review_required'}
        path = folder / 'site.json'
        path.write_text(json.dumps(packet) + '\n', encoding='utf-8')
        return path, packet

    def test_all_case_packets_bind_reviewed_sources(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                with tempfile.TemporaryDirectory(dir=SCRATCH) as dirname:
                    path, packet = self.packet(Path(dirname), case)
                    actual, selected = site_review.reviewed_site(path, packet['case_id'])
                    self.assertEqual(actual['scene']['relation'], case.relation)
                    self.assertEqual(selected, case)

    def test_changed_source_and_missing_review_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as dirname:
            folder = Path(dirname)
            path, packet = self.packet(folder, CASES[0])
            (folder / 'excavation.json').write_text('{"changed":true}\n')
            with self.assertRaisesRegex(ValueError, 'reviewed source changed'):
                site_review.reviewed_site(path, packet['case_id'])
            self.packet(folder, CASES[0])
            packet['review_status'] = 'fixture'
            path.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'provenance missing'):
                site_review.reviewed_site(path, packet['case_id'])

    def test_native_controller_brakes_at_terminal_halt(self):
        class Actor:
            def get_location(self):
                return type('Position', (), {'x': 0, 'y': 0})()

            def get_velocity(self):
                return type('Velocity', (), {'x': 0, 'y': 0, 'z': 0})()

            def get_transform(self):
                position = self.get_location()
                return type('Transform', (), {'location': position,
                                              'rotation': type('Rotation', (), {'yaw': 0})()})()

        control = native_excavation.control_to(Actor(), [0, 0], halt=True)
        self.assertEqual(control['brake'], 1.0)
        self.assertTrue(control['hand_brake'])
        self.assertEqual(native_excavation.control_to(Actor(), [10, 0])['throttle'], 0.25)


if __name__ == '__main__':
    unittest.main()
