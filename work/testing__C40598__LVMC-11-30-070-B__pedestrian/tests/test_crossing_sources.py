"""CPU checks for exact crossing geometry and fail-closed original source gates."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from crosswalk_site import ASSIGNMENT, classify_body, load_review, polygons_intersect
from crossing_measure import measure

ROAD = [[0, 0], [8, 0], [8, 8], [0, 8]]
MARKED = [[1, 0], [4, 0], [4, 8], [1, 8]]
UNMARKED = [[4.5, 0], [7.5, 0], [7.5, 8], [4.5, 8]]


def box(x, y=3):
    return [[x, y], [x + .5, y], [x + .5, y + .5], [x, y + .5]]


class SourceAndCrossingTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ.get('SCENARIO_TEST_TMP_ROOT', '.runtime-work/c40598-tests'))
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + '__marked_crosswalk'
        self.docs = {
            'opendrive': '<OpenDRIVE/>',
            'roadway': {'roadway_id': 'r1', 'roadway_polygon_xy_m': ROAD,
                        'intersection_polygons_xy_m': [ROAD],
                        'public_access_source': 'reviewed dedication record',
                        'jurisdiction_source': 'reviewed municipal map'},
            'crosswalk_inventory': {'roadway_id': 'r1',
                                    'marked_crosswalk_polygons_xy_m': [MARKED],
                                    'unmarked_intersection_crosswalk_polygons_xy_m': [UNMARKED],
                                    'classification_method': 'independent original geometry review'},
            'pedestrian_route': {'roadway_id': 'r1', 'pedestrian_actor_id': 'p1',
                                 'approach_xy_m': [-1, 3], 'exit_xy_m': [9, 3],
                                 'crossing_point_xy_m': [2, 3],
                                 'route_xy_m': [[-1, 3], [2, 3], [9, 3]]},
            'district_frontage': {'roadway_id': 'r1', 'district_type': 'business',
                                  'highway_span_ft': 600,
                                  'reading_assumption': 'review both statutory frontage alternatives; no worker legal classification',
                                  'both_frontage_alternatives_reviewed': True,
                                  'building_frontages': [
                                      {'use': 'business', 'occupied_frontage_ft': 110, 'side': 'north'},
                                      {'use': 'industrial', 'occupied_frontage_ft': 90, 'side': 'south'}]},
            'governing_controls': {'roadway_id': 'r1', 'signs': [], 'signals': []},
            'cameras': {name: {'location_xyz_m': [0, 0, 10],
                              'pitch_yaw_roll_deg': [-30, 0, 0]}
                        for name in ('overview', 'approach', 'reference_corner',
                                     'driver_reference')},
        }
        self.packet = {'assignment_id': ASSIGNMENT, 'case_id': self.case,
                       'cell_id': 'C40598',
                       'source_provenance': {'kind': 'original_reviewed_site',
                                             'diagnostic_fixture': False,
                                             'reviewer': 'fixture reviewer',
                                             'citation': 'synthetic test only'},
                       'sources': {}}
        self._write_sources()

    def _write_sources(self):
        self.packet['sources'] = {}
        for name, value in self.docs.items():
            path = self.root / (name + ('.xodr' if name == 'opendrive' else '.json'))
            path.write_text(value if name == 'opendrive' else json.dumps(value))
            self.packet['sources'][name] = {'path': path.name,
                                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        (self.root / 'review.json').write_text(json.dumps(self.packet))

    def test_reviewed_source_identity_hash_and_context(self):
        result = load_review(self.root / 'review.json', self.root, self.case)
        self.assertEqual(result['sources']['district_frontage']['highway_span_ft'], 600)
        self.docs['district_frontage']['highway_span_ft'] = 599
        self._write_sources()
        with self.assertRaisesRegex(ValueError, '600-foot'):
            load_review(self.root / 'review.json', self.root, self.case)
        self.docs['district_frontage']['highway_span_ft'] = 600
        self._write_sources()
        (self.root / 'district_frontage.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            load_review(self.root / 'review.json', self.root, self.case)

    def test_polygon_edge_and_disjoint_geometry(self):
        self.assertTrue(polygons_intersect(box(3.5), MARKED))
        self.assertFalse(polygons_intersect(box(8.5), MARKED))
        self.assertEqual(classify_body(box(2), self.docs['crosswalk_inventory']),
                         {'marked': True, 'unmarked': False})
        self.assertEqual(classify_body(box(5), self.docs['crosswalk_inventory']),
                         {'marked': False, 'unmarked': True})

    def _observation(self, middle=box(2), *, exit_side='opposite'):
        frames = []
        for i, (body, side) in enumerate(((box(-2), 'start'),
                                          (middle, 'roadway'),
                                          (box(9), exit_side))):
            frames.append({'frame': 100 + i, 'time_s': i * .05,
                           'actor_id': 'p1', 'body_polygon_xy_m': body,
                           'curb_side': side, 'pedestrian_on_roadway': side == 'roadway',
                           'observation_source': 'synthetic_diagnostic'})
        packet = {'assignment_id': ASSIGNMENT, 'case_id': self.case,
                  'original_trace_id': 'synthetic-test-trace', 'diagnostic_fixture': True,
                  'pedestrian_actor_id': 'p1',
                  'site': {'roadway_id': 'r1', 'roadway_polygon_xy_m': ROAD,
                           'crosswalk_inventory': self.docs['crosswalk_inventory'],
                           'district_type': 'business', 'highway_span_ft': 600,
                           'district_source_sha256': 'synthetic-district-hash',
                           'controls_source_sha256': 'synthetic-controls-hash'},
                  'frames': frames}
        path = self.root / 'observations.json'
        path.write_text(json.dumps(packet))
        return path, packet

    def test_complete_crossing_and_both_crosswalk_categories(self):
        path, packet = self._observation()
        self.assertTrue(measure(path)['body_overlaps_marked_crosswalk_each_roadway_frame'])
        packet['frames'][1]['body_polygon_xy_m'] = box(5)
        path.write_text(json.dumps(packet))
        self.assertTrue(measure(path)['body_overlaps_unmarked_crosswalk_each_roadway_frame'])
        packet['frames'][1]['body_polygon_xy_m'] = box(7.6)
        path.write_text(json.dumps(packet))
        self.assertTrue(measure(path)['body_outside_both_each_roadway_frame'])

    def test_reject_missing_opposite_exit_and_stale_occupancy(self):
        path, packet = self._observation(exit_side='start')
        with self.assertRaisesRegex(ValueError, 'complete start-to-opposite'):
            measure(path)
        packet['frames'][2]['curb_side'] = 'opposite'
        packet['frames'][1]['pedestrian_on_roadway'] = False
        path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, 'occupancy differs'):
            measure(path)


if __name__ == '__main__':
    unittest.main()
