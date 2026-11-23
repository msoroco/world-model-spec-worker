import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('signal_exception', ROOT / 'signal_exception.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def source(root, name, body):
    path = root / name
    path.write_text(json.dumps(body))
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class SignalExceptionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        refs = {k: source(self.root, k + '.json', {'kind': k}) for k in
                ('map_ref', 'route_ref', 'signal_ref', 'stop_ref', 'crosswalk_ref', 'cause_ref')}
        refs['cause_ref'] = source(self.root, 'cause_ref.json', {
            'official_head_id': 'head-17', 'actor_type_id': 'vehicle.motorcycle',
            'classification': 'failed_detection', 'source_method': 'native_detector_readback',
            'original_frame_start': 0, 'original_frame_end': 7})
        self.site = {
            'cell_id': 'C111125', 'actor': 'motorcycle_or_moped_operator',
            'maneuver': 'straight', 'control': 'traffic_light',
            'original_sources': refs, 'map_ref': 'map_ref', 'route_ref': 'route_ref',
            'signal_ref': 'signal_ref', 'stop_ref': 'stop_ref', 'crosswalk_ref': 'crosswalk_ref',
            'cause_source_ref': 'cause_ref', 'unchanged_signal_cause': 'failed_detection',
            'ego_approach_id': 'approach-west', 'official_head_id': 'head-17',
            'facing_relation': True, 'route_xy': [[-20, 0], [-5, 0], [5, 0], [20, 0]],
            'straight_tolerance_m': 0.5, 'stop_reference_kind': 'marked_stop_line',
            'stop_reference_station_m': -5, 'intersection_entry_station_m': 0,
            'ego_blueprint_id': 'vehicle.motorcycle', 'ego_classification_source': 'source-17',
            'native_map_name': 'Town', 'spawn_z_m': 0.2, 'approach_yaw_deg': 0,
            'proceed_throttle': 0.2,
        }

    def row(self, frame, station, speed, aspects):
        return {'frame': frame, 'official_head_id': 'head-17',
                'facing_approach_id': 'approach-west', 'actor_id': 'ego-1',
                'actor_type_id': 'vehicle.motorcycle', 'ego_front_station_m': station,
                'speed_mps': speed, 'lit_aspects': aspects}

    def history(self):
        red = ['steady_red', 'green_turn_arrow']
        off = ['steady_red']
        return [self.row(0, -12, 3, red), self.row(1, -6, 0, red),
                self.row(2, -6, 0, off), self.row(3, -6, 0, red),
                self.row(4, -6, 0, off), self.row(5, -6, 0, red),
                self.row(6, 1, 3, red)]

    def test_two_complete_return_cycles_after_stop(self):
        ref = source(self.root, 'events.json', self.history())
        measured = module.measure_attempt(self.site, self.root, ref)
        self.assertEqual(measured['full_cycles_after_stop'], 2)
        self.assertEqual(measured['stopped_frame'], 1)
        self.assertEqual(measured['entry_frame'], 6)
        self.assertIsNone(measured['legal_permission_verdict'])

    def test_early_entry_and_rolling_stop_remain_observable(self):
        rows = self.history()[:4]
        rows[-1]['ego_front_station_m'] = 1
        ref = source(self.root, 'early.json', rows)
        self.assertEqual(module.measure_attempt(self.site, self.root, ref)['full_cycles_after_stop'], 1)
        rows = self.history()
        for row in rows:
            if row['speed_mps'] == 0:
                row['speed_mps'] = 0.1
        ref = source(self.root, 'rolling.json', rows)
        self.assertIsNone(module.measure_attempt(self.site, self.root, ref)['stopped_frame'])

    def test_rejects_unsealed_or_unbound_sources(self):
        ref = source(self.root, 'events.json', self.history())
        bad = dict(ref, sha256='0' * 64)
        with self.assertRaisesRegex(module.SourceError, 'hash mismatch'):
            module.measure_attempt(self.site, self.root, bad)
        rows = self.history()
        rows[3]['official_head_id'] = 'other-head'
        ref = source(self.root, 'wrong-head.json', rows)
        with self.assertRaisesRegex(module.SourceError, 'unbound signal'):
            module.measure_attempt(self.site, self.root, ref)
        no_cause = dict(self.site, cause_source_ref=None)
        with self.assertRaisesRegex(module.SourceError, 'cause has no original source'):
            module.measure_attempt(no_cause, self.root, source(self.root, 'good.json', self.history()))
        refs = dict(self.site['original_sources'])
        refs['cause_ref'] = source(self.root, 'bad-cause.json', {
            'official_head_id': 'head-17', 'actor_type_id': 'vehicle.motorcycle',
            'classification': 'failed_detection', 'source_method': 'unverified_inference',
            'original_frame_start': 0, 'original_frame_end': 7})
        bad_cause = dict(self.site, original_sources=refs)
        with self.assertRaisesRegex(module.SourceError, 'unsupported causal source'):
            module.measure_attempt(bad_cause, self.root, source(self.root, 'good2.json', self.history()))

    def test_rejects_route_and_stopping_reference_drift(self):
        site = dict(self.site, route_xy=[[-20, 0], [-5, 8], [5, 0], [20, 0]])
        with self.assertRaisesRegex(module.SourceError, 'route bends'):
            module.verify_site(site, self.root)
        site = dict(self.site, stop_reference_station_m=3)
        with self.assertRaisesRegex(module.SourceError, 'stop reference after entry'):
            module.verify_site(site, self.root)

    def test_controller_holds_until_sources_and_users_clear(self):
        obs = {'frame': 10, 'official_head_id': 'head-17', 'facing_approach_id': 'approach-west',
               'lit_aspects': ['steady_red', 'green_turn_arrow'], 'ego_front_station_m': -6,
               'stop_and_cycles_verified': False, 'unchanged_signal_cause': 'not_established',
               'other_users': []}
        self.assertEqual(module.control(self.site, obs)['target'], 'hold_before_stop_reference')
        obs.update(stop_and_cycles_verified=True, unchanged_signal_cause='failed_detection')
        self.assertEqual(module.control(self.site, obs)['target'], 'straight_route')
        obs['other_users'] = [{'region': 'adjacent_crosswalk'}]
        self.assertEqual(module.control(self.site, obs)['target'], 'yield_before_entry')
        obs['other_users'] = None
        with self.assertRaisesRegex(module.SourceError, 'other-user'):
            module.control(self.site, obs)

    def test_native_construct_uses_surveyed_route_and_blueprint(self):
        class Obj:
            def __init__(self, **kw): self.__dict__.update(kw)
        class Actor:
            id = 'head-17'
        class World:
            def get_map(self): return Obj(name='Town')
            def get_actors(self): return Obj(filter=lambda pattern: [Actor()])
            def try_spawn_actor(self, bp, pose):
                self.pose = pose
                return Obj(type_id=bp.id, destroy=lambda: None)
        class BP:
            def find(self, value): return Obj(id=value)
        carla = Obj(Location=lambda **kw: Obj(**kw), Rotation=lambda **kw: Obj(**kw),
                    Transform=lambda loc, rot: Obj(location=loc, rotation=rot))
        world = World()
        built = module.construct_native(self.site, self.root, world, carla, BP())
        self.assertEqual(world.pose.location.x, -20)
        self.assertEqual(built['ego'].type_id, 'vehicle.motorcycle')
        with self.assertRaisesRegex(module.SourceError, 'Native map'):
            module.construct_native(dict(self.site, native_map_name='Other'), self.root, world, carla, BP())


if __name__ == '__main__': unittest.main()
