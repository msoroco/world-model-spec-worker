"""CPU tests for the real-context gate; no CARLA import or server contact."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import reviewed_context


class ReviewedContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.road = self.root / 'road.xodr'
        self.road.write_bytes((ROOT/'candidate-map.xodr').read_bytes())
        self.scene = json.loads((ROOT/'scene.json').read_text())

    def test_rejects_missing_review_before_native_import(self):
        with self.assertRaisesRegex(ValueError, 'separately reviewed'):
            reviewed_context(self.scene, self.road)

    def make_packet(self):
        sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        packet = {'assignment_id': self.scene['case_id'].rsplit('__', 1)[0],
                  'map_sha256': sha(self.road), 'reviewer': 'test reviewer',
                  'map_source_citation': 'test map source',
                  'highway_source_citation': 'test highway source',
                  'device_source_citation': 'test device inventory'}
        for key in ('cell_id', 'case_id', 'crossing_id', 'roadway_id',
                    'ego_highway', 'other_highway', 'ego_side', 'other_side',
                    'approach_relation', 'official_device_controls_intersection',
                    'other_left_turn_intent', 'subsection_4_context_reviewed',
                    'intersection_polygon_xy_m', 'ego_route_xyz_m',
                    'other_route_xyz_m'):
            packet[key] = self.scene.get(key)
        packet['crossing_id'] = 'reviewed test crossing'
        packet['roadway_id'] = 'reviewed test roadway'
        packet['official_device_controls_intersection'] = False
        packet['other_left_turn_intent'] = False
        packet['subsection_4_context_reviewed'] = True
        self.scene.update(crossing_id=packet['crossing_id'],
                          roadway_id=packet['roadway_id'],
                          official_device_controls_intersection=False,
                          other_left_turn_intent=False,
                          subsection_4_context_reviewed=True)
        for key in ('map_source', 'highway_source', 'device_source',
                    'intersection_source', 'driver_source'):
            path = self.root / (key+'.txt')
            path.write_text(key+' test evidence\n')
            packet[key] = {'path': path.name, 'sha256': sha(path),
                           'reviewer': 'test reviewer', 'citation': key+' source'}
        source = self.root/'reviewed.json'
        source.write_text(json.dumps(packet))
        self.scene['reviewed_context'] = {'source_path': str(source),
            'sha256': sha(source), 'reviewer': 'test reviewer',
            'source_citation': 'test context packet'}
        return source

    def test_accepts_source_bound_packet_then_rejects_changed_source(self):
        self.make_packet()
        _, packet, retained = reviewed_context(self.scene, self.road)
        self.assertEqual(packet['crossing_id'], 'reviewed test crossing')
        self.assertEqual(len(retained), 5)
        retained['device_source'].write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'device_source source bytes'):
            reviewed_context(self.scene, self.road)

    def test_review_packet_can_resolve_unreviewed_scene_without_mutating_bundle(self):
        source = self.make_packet()
        descriptor = dict(self.scene.pop('reviewed_context'))
        self.scene.pop('crossing_id')
        self.scene.pop('roadway_id')
        self.scene['official_device_controls_intersection'] = 'unreviewed'
        self.scene['subsection_4_context_reviewed'] = False
        path = self.root/'descriptor.json'
        path.write_text(json.dumps(descriptor))
        old = os.environ.get('SCENARIO_REVIEWED_CONTEXT_DESCRIPTOR')
        os.environ['SCENARIO_REVIEWED_CONTEXT_DESCRIPTOR'] = str(path)
        try:
            _, packet, _ = reviewed_context(self.scene, self.road)
            self.assertEqual(packet['crossing_id'], 'reviewed test crossing')
        finally:
            if old is None:
                os.environ.pop('SCENARIO_REVIEWED_CONTEXT_DESCRIPTOR', None)
            else:
                os.environ['SCENARIO_REVIEWED_CONTEXT_DESCRIPTOR'] = old

    def test_rejects_unreviewed_exception(self):
        source = self.make_packet()
        packet = json.loads(source.read_text())
        packet['official_device_controls_intersection'] = True
        source.write_text(json.dumps(packet))
        self.scene['reviewed_context']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        self.scene['official_device_controls_intersection'] = True
        with self.assertRaisesRegex(ValueError, 'exception context unreviewed'):
            reviewed_context(self.scene, self.road)


if __name__ == '__main__':
    unittest.main()
