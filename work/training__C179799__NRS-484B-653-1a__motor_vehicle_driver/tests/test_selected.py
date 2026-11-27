"""CPU source-join, construction, and missing-source tests for selected cases."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import finalize
import runner
from native.person_scene import MODES, inspect, open_drive, require_source_packet


class SelectedPersonInteraction(unittest.TestCase):
    def config(self, suffix):
        return {'case_id': runner.CASE_PREFIX + suffix,
                'selected_case_id': runner.CASE_PREFIX + suffix,
                'law_id': 'NRS-484B-653-1a', 'cell_id': 'C179799',
                'actor': 'motor_vehicle_driver', 'interaction_mode': MODES[suffix],
                'candidate_id': 'primary', 'duration_s': 30, 'rate_hz': 20,
                'cameras': [{'name': n, 'width': w, 'height': h}
                            for n, w, h, *_ in runner.CAMERAS],
                'physical_verified': False, 'legal_verdict': None}

    def packet(self, case_id):
        return {'case_id': case_id, 'access_kind': 'highway',
                'highway_or_public_access_source': 'synthetic diagnostic road context',
                'driver_identity_source': 'synthetic diagnostic driver',
                'vehicle_class_source': 'synthetic conventional vehicle',
                'worker_identity_source': 'synthetic diagnostic person actor',
                'worker_role_source': 'synthetic roadside worker request',
                'worker_route_relation_source': 'synthetic route-side offset',
                'sight_line_source': 'synthetic unobstructed authored geometry only',
                'surface_condition_source': 'synthetic dry road request',
                'nearby_property_source': 'synthetic empty surrounding scene',
                'physical_verified': False, 'legal_verdict': None}

    def make_fixture(self, root, suffix):
        config = self.config(suffix)
        (root / 'config.json').write_text(json.dumps(config) + '\n')
        (root / 'original-context-packet.json').write_text(json.dumps(self.packet(config['case_id'])) + '\n')
        (root / 'native-road-readback.json').write_text(json.dumps({
            'driving_road_id': 1, 'driving_lane_id': -1}) + '\n')
        with (root / 'native-person-interaction.jsonl').open('w') as raw, (
                root / 'video_frames.jsonl').open('w') as mapping:
            for index in range(600):
                time = index/20
                x = -78 + 8*time
                row = {'frame': index, 'native_frame': 1000+index,
                       'time_s': time, 'ego_actor_id': 1,
                       'ego_blueprint_id': 'vehicle.synthetic', 'ego_x_m': x,
                       'ego_y_m': -1.75, 'ego_vx_mps': 8, 'ego_vy_mps': 0,
                       'ego_radius_m': 1, 'ego_accel_longitudinal_mps2': 0,
                       'ego_yaw_rate_radps': 0, 'person_actor_id': 2,
                       'person_blueprint_id': 'walker.pedestrian.synthetic',
                       'person_x_m': 4, 'person_y_m': -5.2,
                       'person_vx_mps': 0, 'person_vy_mps': 0,
                       'person_radius_m': .4, 'collision_sensor_contact': False}
                raw.write(json.dumps(row) + '\n')
                mapping.write(json.dumps({'video_frame': index, 'native_frame': 1000+index,
                    'time_s': time, 'camera_native_frames': {
                        name: 1000+index for name, *_ in runner.CAMERAS}}) + '\n')
        return config

    def test_geometry_and_source_requirements(self):
        self.assertEqual(inspect()['driving_lane_id'], -1)
        self.assertIn('<OpenDRIVE>', open_drive())
        for suffix in MODES:
            self.assertEqual(runner.check(self.config(suffix))['frames'], 600)
            packet = self.packet(self.config(suffix)['case_id'])
            self.assertEqual(require_source_packet(packet, packet['case_id']), packet)
            with self.assertRaisesRegex(ValueError, 'public-access.*source'):
                require_source_packet(dict(packet, highway_or_public_access_source=''), packet['case_id'])
            with self.assertRaisesRegex(ValueError, 'exclusions'):
                require_source_packet(dict(packet, access_kind='public_access_premises'), packet['case_id'])

    def test_saved_source_join_and_negative(self):
        scratch = Path(os.environ['TMPDIR']).resolve()
        with tempfile.TemporaryDirectory(prefix='c179799-', dir=scratch) as temporary:
            root = Path(temporary)
            for suffix in MODES:
                attempt = root / suffix
                attempt.mkdir()
                self.make_fixture(attempt, suffix)
                result = finalize.analyze(attempt)
                self.assertEqual(result['case_id'], runner.CASE_PREFIX + suffix)
                self.assertEqual(result['selected_branch_measurement']['frames'], 600)
                self.assertIsNone(result['mental_state_conclusion'])
                raw = attempt / 'native-person-interaction.jsonl'
                lines = raw.read_text().splitlines()
                lines[5] = json.dumps(dict(json.loads(lines[5]), person_actor_id=1))
                raw.write_text('\n'.join(lines) + '\n')
                with self.assertRaisesRegex(ValueError, 'distinct vehicle/person'):
                    finalize.analyze(attempt)
                raw.write_text('\n'.join(lines[:5] + [json.dumps(dict(json.loads(lines[5]), person_actor_id=2))] + lines[6:]) + '\n')
                packet = attempt / 'original-context-packet.json'
                packet.unlink()
                with self.assertRaisesRegex(ValueError, 'Missing required source: original-context-packet.json'):
                    finalize.analyze(attempt)


if __name__ == '__main__':
    unittest.main()
