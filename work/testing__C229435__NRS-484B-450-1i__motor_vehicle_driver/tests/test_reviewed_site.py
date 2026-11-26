"""Exercise reviewed original railroad geometry and source gate."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from reviewed_site import load_review, nearest_distance

ASSIGNMENT = 'testing__C229435__NRS-484B-450-1i__motor_vehicle_driver'
CASE = ASSIGNMENT + '__inside_no_exception'


class ReviewedRailroadTests(unittest.TestCase):
    def test_nearest_planned_footprint(self):
        rails = [{'rail_id': 'one', 'points_m': [[0, -10], [0, 10]]}]
        self.assertEqual(nearest_distance([[14, -1], [18, -1], [18, 1], [14, 1]], rails), 14)

    def test_original_packet_and_missing_carrier(self):
        root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        with tempfile.TemporaryDirectory(dir=root) as temp:
            source_root = Path(temp)
            sources = {
                'opendrive': '<OpenDRIVE/>',
                'rail_inventory': {'railroad_identity': 'reviewed-track',
                    'carrier_provenance': 'external railroad map review',
                    'rail_polylines_m': [{'rail_id': 'one', 'points_m': [[0, -10], [0, 10]]}]},
                'ego_plan': {'ego_actor_id': 'ego', 'route_xy_m': [[25, 0], [16, 0]],
                    'parking_footprint_xy_m': [[14, -1], [18, -1], [18, 1], [14, 1]],
                    'vehicle_action': 'park'},
                'other_vehicle_plan': {'vehicle_actor_id': 'other', 'route_xy_m': [[30, 3], [20, 3]],
                    'motion_plan': 'reviewed other vehicle route'},
                'exception_review': {'traffic_conflict_necessity': 'absent',
                    'law_compliance': 'absent', 'officer_direction': 'absent',
                    'official_device_direction': 'absent', 'source_review': 'external review'},
                'cameras': {name: {'location_xyz_m': [0, 0, 10],
                    'pitch_yaw_roll_deg': [0, 0, 0]} for name in
                    ('overview', 'approach', 'reference_corner', 'driver_reference')}}
            bindings = {}
            for name, value in sources.items():
                path = source_root / (name + ('.xodr' if name == 'opendrive' else '.json'))
                path.write_text(value if name == 'opendrive' else json.dumps(value) + '\n')
                bindings[name] = {'path': path.name,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            packet = source_root / 'review.json'
            review = {'assignment_id': ASSIGNMENT, 'case_id': CASE, 'cell_id': 'C229435',
                'source_provenance': {'kind': 'original_reviewed_site',
                    'diagnostic_fixture': False, 'reviewer': 'synthetic protocol reviewer',
                    'citation': 'synthetic protocol fixture'}, 'sources': bindings}
            packet.write_text(json.dumps(review) + '\n')
            self.assertEqual(load_review(packet, source_root, CASE, 14)['planned_nearest_rail_distance_m'], 14)
            sources['rail_inventory']['carrier_provenance'] = ''
            (source_root / 'rail_inventory.json').write_text(json.dumps(sources['rail_inventory']) + '\n')
            with self.assertRaisesRegex(ValueError, 'path/hash differs'):
                load_review(packet, source_root, CASE, 14)


if __name__ == '__main__':
    unittest.main()
