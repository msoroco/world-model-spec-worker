import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('c80909_runner', ROOT / 'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_native_capture_restores_world_before_sealing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet, _, plan = self.plan(root)
            output = root / 'attempt'
            output.mkdir()
            (output / 'construction.json').write_text('{}\n')
            events = []
            settings = types.SimpleNamespace(synchronous_mode=False,
                                             fixed_delta_seconds=None)
            world = types.SimpleNamespace(
                get_settings=lambda: settings,
                apply_settings=lambda value: events.append(('settings', value.synchronous_mode)))
            client = types.SimpleNamespace(
                set_timeout=lambda value: events.append(('timeout', value)),
                get_world=lambda: world)
            carla = types.ModuleType('carla')
            carla.Client = lambda host, port: client
            exchange = types.ModuleType('worker_exchange')
            exchange.__path__ = []
            native = types.ModuleType('worker_exchange.native_output')
            native.seal_capture = lambda *a, **kw: events.append(('seal', kw['frames']))
            restore_module = types.ModuleType('worker_exchange.world_restore')
            restore_module.snapshot = lambda c: events.append(('snapshot', c)) or {'saved': True}
            restore_module.restore = lambda c, s: events.append(('restore', s)) or {'restored': True}
            modules = {'carla': carla, 'worker_exchange': exchange,
                       'worker_exchange.native_output': native,
                       'worker_exchange.world_restore': restore_module}
            argv = ['runner.py', '--site-plan', str(packet), '--config', str(root / 'absent.json'),
                    '--output-dir', str(output)]
            with patch.dict(sys.modules, modules), patch.object(sys, 'argv', argv), \
                 patch.object(runner, 'run', side_effect=lambda *args: events.append(('run', plan['frames'])) or {'overview': 0}):
                runner.main()
            self.assertEqual([event[0] for event in events if event[0] in
                              ('snapshot', 'run', 'restore', 'seal')],
                             ['snapshot', 'run', 'restore', 'seal'])
            self.assertEqual(events[-1], ('seal', 600))

    def test_native_capture_failure_restores_and_records_unsealed_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet, _, _ = self.plan(root)
            output = root / 'attempt'
            output.mkdir()
            (output / 'construction.json').write_text('{}\n')
            events = []
            world = types.SimpleNamespace(
                get_settings=lambda: types.SimpleNamespace(synchronous_mode=False,
                                                           fixed_delta_seconds=None),
                apply_settings=lambda value: None)
            client = types.SimpleNamespace(set_timeout=lambda value: None,
                                           get_world=lambda: world)
            carla = types.ModuleType('carla')
            carla.Client = lambda host, port: client
            exchange = types.ModuleType('worker_exchange')
            exchange.__path__ = []
            native = types.ModuleType('worker_exchange.native_output')
            native.seal_capture = lambda *a, **kw: self.fail('Failed capture was sealed')
            restore_module = types.ModuleType('worker_exchange.world_restore')
            restore_module.snapshot = lambda c: {'saved': True}
            restore_module.restore = lambda c, s: events.append('restore') or {'restored': True}
            modules = {'carla': carla, 'worker_exchange': exchange,
                       'worker_exchange.native_output': native,
                       'worker_exchange.world_restore': restore_module}
            argv = ['runner.py', '--site-plan', str(packet), '--config', str(root / 'absent.json'),
                    '--output-dir', str(output)]
            with patch.dict(sys.modules, modules), patch.object(sys, 'argv', argv), \
                 patch.object(runner, 'run', side_effect=ValueError('capture failed')):
                with self.assertRaisesRegex(ValueError, 'capture failed'):
                    runner.main()
            self.assertEqual(events, ['restore'])
            status = json.loads((output / 'native-run-status.json').read_text())
            self.assertFalse(status['capture_sealed'])
            self.assertEqual(status['errors'], ['capture failed'])

    def plan(self, root):
        source = root / 'review.txt'
        source.write_text('Reviewed source fixture for CPU contract test.\n')
        context = {'native_map_id': 'TownX',
                   'divided_highway_source': 'review.txt',
                   'roadway_boundaries_source': 'review.txt',
                   'opening_geometry_source': 'review.txt',
                   'barrier_actors_source': 'review.txt',
                   'other_vehicle_source': 'review.txt',
                   'right_hand_roadway_xy_m': [[0,-10],[30,-10],[30,-2],[0,-2]],
                   'destination_roadway_xy_m': [[0,2],[30,2],[30,10],[0,10]],
                   'dividing_space_xy_m': [[0,-2],[30,-2],[30,2],[0,2]],
                   'opening_xy_m': [[10,-2],[20,-2],[20,2],[10,2]]}
        plan = {'assignment_id': runner.ASSIGNMENT, 'selected_case_id': runner.CASE,
                'source_review_status': 'reviewed_original_map_and_cameras',
                'rate_hz': 20, 'frames': 600, 'native_map_name': 'TownX',
                'source_refs': [{'path': 'review.txt',
                                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}],
                'divider_context': context,
                'camera_poses': {name: [0,0,3,0,0,0] for name in runner.CAMERAS},
                'barrier_sections': [{'blueprint_id': 'barrier', 'pose': [0,0,0,0,0,0]}]*2,
                'ego_spawn_pose': [5,-5,0,0,0,0],
                'other_spawn_pose': [26,-5,0,0,0,0],
                'ego_route_xy_m': [[5,-5],[15,-5],[15,0],[15,5]],
                'ego_body_radius_m': 1.0,
                'other_route_xy_m': [[26,-5],[27,-5]],
                'vehicle_blueprint_id': 'vehicle.test',
                'barrier_axis_xy': [1,0],
                'native_spawn_lanes': {'ego': {'road_id': 1, 'lane_id': 1},
                                       'other': {'road_id': 1, 'lane_id': 1}}}
        packet = root / 'site.json'
        packet.write_text(json.dumps(plan))
        return packet, source, plan

    def test_blocked_and_continuation_case_routes_are_exactly_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            packet, source, plan = self.plan(Path(directory))
            plan['selected_case_id'] = runner.BLOCKED_CASE
            plan['ego_route_xy_m'] = [[5,-5],[9,-5],[9,0],[9,5]]
            plan['ego_body_radius_m'] = .4
            plan['planned_barrier_footprints_xy_m'] = [
                [[0,-2],[8,-2],[8,2],[0,2]],
                [[22,-2],[30,-2],[30,2],[22,2]]]
            packet.write_text(json.dumps(plan))
            self.assertEqual(runner.load_plan(packet)['selected_case_id'], runner.BLOCKED_CASE)
            plan['ego_route_xy_m'] = [[5,-5],[7,-5],[7,0],[7,5]]
            packet.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'collides with physical barrier'):
                runner.load_plan(packet)
            plan['selected_case_id'] = runner.CONTINUE_CASE
            plan['ego_route_xy_m'] = [[5,-5],[15,-5],[25,-5]]
            packet.write_text(json.dumps(plan))
            self.assertEqual(runner.load_plan(packet)['selected_case_id'], runner.CONTINUE_CASE)
            plan['selected_case_id'] = runner.ASSIGNMENT + '__unplanned'
            packet.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'Exact C80909'):
                runner.load_plan(packet)

    def test_crossover_case_requires_separate_hashed_authority_source(self):
        with tempfile.TemporaryDirectory() as directory:
            packet, _, plan = self.plan(Path(directory))
            authority = Path(directory) / 'authority.txt'
            authority.write_text('CPU fixture for source binding; no public-authority fact asserted.\n')
            ref = {'path': 'authority.txt',
                   'sha256': hashlib.sha256(authority.read_bytes()).hexdigest()}
            plan['selected_case_id'] = runner.CROSSOVER_CASE
            plan['authority_source_ref'] = ref
            plan['source_refs'].append(ref)
            plan['crossover_xy_m'] = [[10,-2],[20,-2],[20,2],[10,2]]
            packet.write_text(json.dumps(plan))
            self.assertEqual(runner.load_plan(packet)['selected_case_id'], runner.CROSSOVER_CASE)
            plan['authority_source_ref'] = {'path': 'absent.txt', 'sha256': ref['sha256']}
            packet.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'public-authority review'):
                runner.load_plan(packet)
            plan['authority_source_ref'] = ref
            plan['crossover_xy_m'] = [[22,-2],[24,-2],[24,2],[22,2]]
            packet.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'misses sourced crossover'):
                runner.load_plan(packet)

    def test_reviewed_source_bound_opening_plan_and_negative_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            packet, source, plan = self.plan(Path(directory))
            self.assertEqual(runner.load_plan(packet)['frames'], 600)
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                runner.load_plan(packet)
            packet, source, plan = self.plan(Path(directory))
            plan['source_review_status'] = 'unreviewed'
            packet.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'Reviewed original'):
                runner.load_plan(packet)
            plan['source_review_status'] = 'reviewed_original_map_and_cameras'
            plan['ego_route_xy_m'] = [[5,-5],[5,-3],[5,0],[5,5]]
            packet.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'blocked dividing space'):
                runner.load_plan(packet)


if __name__ == '__main__': unittest.main()
