import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_turn_c111610', ROOT / 'native_turn.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeTurnTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = {
            'map': {'intersection_id': 'junction-1', 'lane_ids': [1, 2, 3]},
            'ego_signal': {'head_id': 'ego-head', 'governed_lane_ids': [1]},
            'opposing_signal': {'head_id': 'opp-head'},
            'crosswalk': {'crosswalk_id': 'cw-1', 'adjacent_to_turn': True,
                          'polygon_xy': [[0, 0], [2, 0], [2, 2], [0, 2]]},
            'pedestrian_permission': {'crosswalk_id': 'cw-1', 'source_id': 'ped-head',
                                      'lawfulness_basis': 'walk_device'},
            'other_traffic': {'actor_id': 92, 'intersection_id': 'junction-1', 'route_lane_id': 3},
        }
        self.refs = {name: self.save(name, value) for name, value in self.data.items()}
        self.site = {'cell_id': 'C111610', 'actor': 'motor_vehicle_driver',
                     'intersection_id': 'junction-1', 'ego_approach_lane_id': 1,
                     'arrow_destination_lane_id': 2, 'straight_destination_lane_id': 3,
                     'ego_head_id': 'ego-head', 'opposing_head_id': 'opp-head',
                     'adjacent_crosswalk_id': 'cw-1', 'arrow_direction': 'left',
                     'pedestrian_actor_id': 91, 'original_sources': self.refs}
        self.site['other_traffic_actor_id'] = 92

    def save(self, name, value):
        path = self.root / (name + '.json')
        path.write_text(json.dumps(value))
        return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def frames(self):
        return [{'frame': i, 'ego_head_id': 'ego-head', 'opposing_head_id': 'opp-head',
                 'ego_red': True, 'opposing_red': True, 'ego_arrow_direction': 'left',
                 'pedestrian_actor_id': 91, 'pedestrian_permission_source_id': 'ped-head',
                 'other_traffic_actor_id': 92, 'other_traffic_lawful_context': True,
                 'other_traffic_in_intersection': False,
                 'pedestrian_lawful_context': True, 'pedestrian_xy': [1, 1],
                 'ego_route_lane_id': 2, 'ego_in_intersection': i == 1,
                 'ego_speed_mps': 2.0} for i in range(2)]

    def test_source_gated_measurement(self):
        result = native.measure_attempt(self.site, self.root, self.save('frames', self.frames()))
        self.assertEqual(result['first_ego_entry']['frame'], 1)
        self.assertTrue(result['first_ego_entry']['pedestrian_inside_adjacent_crosswalk'])
        self.assertIsNone(result['legal_verdict'])

    def test_signal_and_source_fail_closed(self):
        rows = self.frames()
        rows[1]['opposing_red'] = False
        with self.assertRaisesRegex(native.SourceError, 'opposing steady red'):
            native.measure_attempt(self.site, self.root, self.save('bad', rows))
        self.site['original_sources']['map']['sha256'] = '0' * 64
        with self.assertRaisesRegex(native.SourceError, 'hash mismatch'):
            native.verify_site(self.site, self.root)

    def test_movement_and_adjacency(self):
        self.assertEqual(native.case_command('yield_pedestrian', True)['controller_policy'], 'hold_until_clear')
        self.assertEqual(native.case_command('wrong_movement', False)['route'], 'straight')
        with self.assertRaises(native.SourceError):
            native.case_command('continue_pedestrian', False)
        self.site['arrow_destination_lane_id'] = 3
        with self.assertRaisesRegex(native.SourceError, 'different movements'):
            native.verify_site(self.site, self.root)
        self.site['arrow_destination_lane_id'] = 2
        self.data['crosswalk']['adjacent_to_turn'] = False
        self.site['original_sources']['crosswalk'] = self.save('crosswalk', self.data['crosswalk'])
        with self.assertRaisesRegex(native.SourceError, 'adjacency'):
            native.verify_site(self.site, self.root)

    def test_native_spawn_and_cleanup(self):
        class Actor:
            def __init__(self):
                self.destroyed = False
            def destroy(self):
                self.destroyed = True
        class World:
            def __init__(self, fail_at=None):
                self.actors = []
                self.fail_at = fail_at
            def try_spawn_actor(self, blueprint, transform):
                if len(self.actors) == self.fail_at:
                    return None
                actor = Actor()
                self.actors.append(actor)
                return actor
        class Library:
            def find(self, key):
                return key
        class Carla:
            class Location:
                def __init__(self, *xyz):
                    self.xyz = xyz
            class Rotation:
                def __init__(self, yaw):
                    self.yaw = yaw
            class Transform:
                def __init__(self, location, rotation):
                    self.location, self.rotation = location, rotation
        sources = {}
        plan = {}
        for role, blueprint in [('ego', 'vehicle.ego'), ('pedestrian', 'walker.ped'), ('other_traffic', 'vehicle.other')]:
            sources[role] = self.save('spawn_' + role, {'spawn_role': role, 'blueprint_id': blueprint,
                                                        'spawn_xyz': [1, 2, 0], 'spawn_yaw': 90})
            plan[role] = {'source_ref': role, 'blueprint_id': blueprint,
                          'actor_id': 91 if role == 'pedestrian' else 92}
        self.site['spawn_sources'] = sources
        world = World()
        output = native.construct_native(self.site, self.root, world, Library(), Carla, 'yield_pedestrian', plan)
        self.assertEqual(set(output['actors']), {'ego', 'pedestrian', 'other_traffic'})
        self.assertEqual(output['command']['controller_policy'], 'hold_until_clear')
        failed = World(fail_at=2)
        with self.assertRaisesRegex(native.SourceError, 'spawn failed'):
            native.construct_native(self.site, self.root, failed, Library(), Carla, 'yield_pedestrian', plan)
        self.assertTrue(all(actor.destroyed for actor in failed.actors))

    def test_controller_and_measured_precedence(self):
        command = native.case_command('yield_pedestrian', True)
        self.assertEqual(native.controller_step(command, True, False)['brake'], 1.0)
        self.assertEqual(native.controller_step(command, False, False)['throttle'], 0.25)
        rows = self.frames()
        rows[1]['pedestrian_xy'] = [5, 5]
        measured = native.measure_attempt(self.site, self.root, self.save('yield_frames', rows))
        self.assertEqual(native.audit_case_measurement('yield_pedestrian', measured)['first_entry_frame'], 1)
        with self.assertRaisesRegex(native.SourceError, 'precedence difference'):
            native.audit_case_measurement('continue_pedestrian', measured)
        rows[1]['pedestrian_xy'] = [1, 1]
        measured = native.measure_attempt(self.site, self.root, self.save('continue_frames', rows))
        self.assertEqual(native.audit_case_measurement('continue_pedestrian', measured)['first_entry_frame'], 1)

    def test_other_traffic_precedence_and_route(self):
        rows = self.frames()
        for row in rows:
            row['pedestrian_xy'] = [5, 5]
        rows[0]['other_traffic_in_intersection'] = True
        measured = native.measure_attempt(self.site, self.root, self.save('other_yield', rows))
        self.assertEqual(native.audit_case_measurement('yield_other_traffic', measured)['first_entry_frame'], 1)
        rows[1]['other_traffic_in_intersection'] = True
        measured = native.measure_attempt(self.site, self.root, self.save('other_continue', rows))
        self.assertEqual(native.audit_case_measurement('continue_other_traffic', measured)['first_entry_frame'], 1)
        with self.assertRaisesRegex(native.SourceError, 'precedence difference'):
            native.audit_case_measurement('yield_other_traffic', measured)
        rows[1]['other_traffic_in_intersection'] = False
        rows[1]['ego_route_lane_id'] = 3
        measured = native.measure_attempt(self.site, self.root, self.save('wrong_route', rows))
        self.assertEqual(native.audit_case_measurement('wrong_movement', measured)['first_entry_frame'], 1)


if __name__ == '__main__':
    unittest.main()
