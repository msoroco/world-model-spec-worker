import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner


def config():
    polygon = [[10, -5], [20, -5], [20, 5], [10, 5]]
    return {
        'selected_case_id': runner.PRIMARY, 'law_id': 'NRS-484B-250-2',
        'cell_id': 'C125697', 'actor': 'motor_vehicle_driver',
        'rate_hz': 20, 'duration_s': 45, 'other_approach_side': 'right',
        'required_atoms': [], 'recording_description': {},
        'ego_release_frame': 20, 'other_release_frame': 20,
        'ego_target_speed_mps': 5, 'other_target_speed_mps': 5,
        'site': {
            'native_map_name': 'TownX', 'crossing_id': 44,
            'ego_highway_id': 'east-west', 'other_highway_id': 'north-south',
            'same_statutory_crossing': True,
            'crossing_polygon_xy_m': polygon,
            'crossing_polygon_source': 'source review of one median crossing',
            'approach_geometry_source': 'source reviewed route',
            'median_spacing_source': 'source reviewed roadway opening',
            'all_entrances_source': 'source reviewed entrance inventory',
            'signal_governance_source': 'source reviewed affected lanes',
            'signal_head_video_source': 'source reviewed camera plan',
            'ego_approach': [0, 0, 0, 0], 'ego_entry': [12, 0, 0, 0],
            'other_approach': [15, -12, 0, 90],
            'other_entry': [15, -3, 0, 90],
            'routes': {'ego': [[0, 0], [12, 0], [15, 0], [24, 0]],
                       'other': [[15, -12], [15, -3], [15, 0], [15, 8]]},
            'entrance_road_lanes': [[1, -1], [2, -1]],
            'cameras': {name: [0, 0, 10, 0, -30, 0] for name in runner.CAMERAS},
        },
    }


def write_review(root, value, omit_claim=None):
    site = value['site']
    claims = {
        'crossing_polygon_source': ['native_map_name', 'crossing_id',
                                    'crossing_polygon_xy_m', 'same_statutory_crossing'],
        'approach_geometry_source': ['ego_highway_id', 'other_highway_id'],
        'median_spacing_source': ['same_statutory_crossing'],
        'all_entrances_source': ['entrance_road_lanes'],
        'signal_governance_source': ['entrance_road_lanes'],
        'signal_head_video_source': ['entrance_road_lanes'],
    }
    docs = {}
    for field, keys in claims.items():
        filename = field + '.json'
        site[field] = filename
        reviewed = {key: site[key] for key in keys if (field, key) != omit_claim}
        path = root / filename
        path.write_text(json.dumps({'format': 'worker-median-site-source',
                                    'source_role': field,
                                    'review_basis': 'synthetic CPU schema test',
                                    'reviewed_site_fields': reviewed}))
        docs[field] = {'path': filename,
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    packet = root / 'site-review.json'
    packet.write_text(json.dumps({'format': 'worker-median-site-review',
                                  'review_status': 'reviewed_candidate',
                                  'site': site, 'source_documents': docs}))
    value['site_review'] = {'path': packet.name,
                            'sha256': hashlib.sha256(packet.read_bytes()).hexdigest()}
    return packet


class RunnerTests(unittest.TestCase):
    def test_cpu_check_exact_primary_is_lazy(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config.json'
            value = config()
            write_review(path.parent, value)
            path.write_text(json.dumps(value))
            completed = subprocess.run(
                [sys.executable, str(ROOT / 'runner.py'), '--config', str(path), '--check'],
                capture_output=True, text=True, check=True)
        report = json.loads(completed.stdout)
        self.assertEqual(report['planned_frames'], 900)
        self.assertEqual(set(report['named_source_cameras']), set(runner.CAMERAS))
        self.assertFalse(report['carla_started'])

    def test_materialized_offline_entrypoint_uses_local_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = config()
            write_review(root, value)
            (root / 'config.json').write_text(json.dumps(value))
            completed = subprocess.run(
                [sys.executable, str(ROOT / 'runner.py'), '--check'],
                cwd=root, capture_output=True, text=True, check=True)
            self.assertTrue(json.loads(completed.stdout)['cpu_check_passed'])

    def test_missing_camera_or_crossing_route_rejected(self):
        value = config()
        del value['site']['cameras']['overview']
        with self.assertRaisesRegex(ValueError, 'four source-camera'):
            runner.validate_config(value)
        value = config()
        value['site']['routes']['ego'] = [[0, 0], [12, 8], [24, 8]]
        value['site']['ego_entry'] = [12, 8, 0, 0]
        with self.assertRaisesRegex(ValueError, 'crossing interior'):
            runner.validate_config(value)

    def test_source_frame_join_rejects_skip(self):
        queue = Queue()
        queue.put(NS(frame=5))
        self.assertEqual(runner._sensor_frame(queue, 5).frame, 5)
        queue.put(NS(frame=7))
        with self.assertRaisesRegex(ValueError, 'skipped'):
            runner._sensor_frame(queue, 6)

    def test_drive_hold_and_release_commands(self):
        class Vehicle:
            def __init__(self):
                self.last = None

            def get_velocity(self):
                return NS(x=0.0, y=0.0, z=0.0)

            def apply_control(self, command):
                self.last = command

        vehicle = Vehicle()
        carla = NS(VehicleControl=lambda: NS())
        runner._drive(carla, vehicle, 5, True, .25)
        self.assertEqual(vehicle.last.brake, 1.0)
        self.assertEqual(vehicle.last.throttle, 0.0)
        runner._drive(carla, vehicle, 5, False, -.25)
        self.assertEqual(vehicle.last.brake, 0.0)
        self.assertGreater(vehicle.last.throttle, 0.0)
        self.assertEqual(vehicle.last.steer, -.25)

    def test_site_packet_rejects_changed_source_and_missing_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = config()
            write_review(root, value)
            runner.validate_config(value, root)
            (root / value['site']['median_spacing_source']).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'missing or changed'):
                runner.validate_config(value, root)
            value = config()
            write_review(root, value, omit_claim=('all_entrances_source',
                                                  'entrance_road_lanes'))
            with self.assertRaisesRegex(ValueError, 'Missing reviewed source claims'):
                runner.validate_config(value, root)


if __name__ == '__main__':
    unittest.main()
