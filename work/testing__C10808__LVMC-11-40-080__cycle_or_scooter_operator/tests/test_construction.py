import importlib.util
import json
from pathlib import Path
import unittest

FOLDER = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', FOLDER / 'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Library:
    def filter(self, pattern):
        return [pattern] if pattern in {'static.prop.sign.no_uturn', 'static.prop.bicycle', 'walker.pedestrian.*'} else []


class World:
    def __init__(self):
        self.calls = []
    def get_blueprint_library(self):
        return Library()
    def spawn_actor(self, blueprint, transform):
        self.calls.append((blueprint, transform))
        return {'blueprint': blueprint}


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        self.scene = runner.load_scene()

    def test_dismount_precedes_reversal(self):
        points = runner.path_points(self.scene)
        self.assertEqual(points['mounted'][-1], points['afoot'][0])
        self.assertLess(self.scene['dismount_x_m'], self.scene['turn_x_m'])
        self.assertLess(points['afoot'][-1][0], self.scene['turn_x_m'])
        self.assertEqual(runner.phase_at(self.scene, self.scene['turn_x_m'], 0), 'dismount_hold')
        self.assertEqual(runner.phase_at(self.scene, self.scene['turn_x_m'], 2), 'afoot_reversal')

    def test_both_trajectory_directions_and_body_separation(self):
        start = runner.trajectory(self.scene, 0)
        hold = runner.trajectory(self.scene, 6)
        afoot = runner.trajectory(self.scene, 10)
        finish = runner.trajectory(self.scene, 29)
        self.assertEqual(start['phase'], 'mounted_approach')
        self.assertEqual(hold['phase'], 'dismount_hold')
        self.assertEqual(afoot['phase'], 'afoot_reversal')
        self.assertLess(finish['operator'][0], self.scene['turn_x_m'])
        self.assertEqual(finish['phase'], 'turn_complete')
        self.assertGreater(abs(afoot['operator'][0]-afoot['bicycle'][0]), 1)
        mounted = dict(self.scene,dismount_enabled=False)
        mounted_finish = runner.trajectory(mounted, 20)
        self.assertEqual(mounted_finish['phase'], 'turn_complete')
        self.assertEqual(mounted_finish['operator'], mounted_finish['bicycle'])

    def test_sign_bike_and_same_operator_are_spawned(self):
        self.scene['sign']['blueprint_filter'] = 'static.prop.sign.no_uturn'
        world = World()
        actors = runner.spawn_scene(world, self.scene, lambda *parts: parts)
        self.assertEqual(set(actors), {'sign','bicycle','operator'})
        self.assertEqual([c[0] for c in world.calls], ['static.prop.sign.no_uturn','static.prop.bicycle','walker.pedestrian.*'])
        self.assertLess(world.calls[0][1][0], self.scene['dismount_x_m'])

    def test_rejects_non_sign_and_missing_blueprint(self):
        world = World()
        self.scene['sign']['blueprint_filter'] = 'static.prop.trafficcone01'
        with self.assertRaisesRegex(ValueError, 'not a prohibition sign'):
            runner.spawn_scene(world, self.scene, lambda *parts: parts)
        self.scene['sign']['blueprint_filter'] = 'static.prop.sign.no_uturn'
        self.scene['bicycle']['blueprint_filter'] = 'missing.bicycle'
        with self.assertRaisesRegex(ValueError, 'blueprint unavailable'):
            runner.spawn_scene(world, self.scene, lambda *parts: parts)

    def test_partial_actor_spawn_releases_earlier_assets(self):
        destroyed = []
        actors = iter([type('Actor', (), {'destroy': lambda self: destroyed.append('sign')})(), None])
        world = World()
        world.spawn_actor = lambda blueprint, transform: next(actors)
        with self.assertRaisesRegex(ValueError, 'Native actor spawn failed: bicycle'):
            runner.spawn_scene(world, self.scene, lambda *parts: parts)
        self.assertEqual(destroyed, ['sign'])


if __name__ == '__main__':
    unittest.main()

spec_audit = importlib.util.spec_from_file_location('comparison_audit', FOLDER / 'comparison_audit.py')
comparison_audit = importlib.util.module_from_spec(spec_audit)
spec_audit.loader.exec_module(comparison_audit)


class ComparisonAuditTests(unittest.TestCase):
    def evidence(self, dismounted):
        fixed = {key: 'same-source-value' for key in comparison_audit.FIXED}
        fixed['duration_s'] = 30
        values = {'observed_sign': {'message': 'NO U TURN', 'erected': True},
                  'turn_start_s': 10.0, 'turn_complete_s': 16.0}
        if dismounted:
            values.update(dismount_time_s=8.0, afoot_body_samples=[{'time_s': 9.0}])
        else:
            values.update(mounted_body_samples=[{'time_s': 10.0}])
        fixed.update(values)
        fixed['sources'] = {key: {'kind': 'original_native', 'path': 'native.jsonl', 'sha256': 'a'*64}
                            for key in values}
        return fixed

    def test_positive_measured_comparison(self):
        self.assertTrue(comparison_audit.audit(self.evidence(True), self.evidence(False))['passed'])

    def test_rejects_missing_evidence(self):
        dismounted = self.evidence(True)
        del dismounted['sources']['afoot_body_samples']
        with self.assertRaisesRegex(ValueError, 'missing original Native evidence'):
            comparison_audit.audit(dismounted, self.evidence(False))

    def test_rejects_changed_fixed_condition(self):
        mounted = self.evidence(False)
        mounted['alley_geometry_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'fixed condition differs'):
            comparison_audit.audit(self.evidence(True), mounted)

    def test_rejects_late_dismount(self):
        dismounted = self.evidence(True)
        dismounted['dismount_time_s'] = 11.0
        with self.assertRaisesRegex(ValueError, 'dismount not observed before reversal'):
            comparison_audit.audit(dismounted, self.evidence(False))

import hashlib
import tempfile
spec_analysis = importlib.util.spec_from_file_location('analysis', FOLDER / 'analysis.py')
analysis = importlib.util.module_from_spec(spec_analysis)
spec_analysis.loader.exec_module(analysis)


class SavedAnalysisTests(unittest.TestCase):
    def attempt(self, root, dismounted=True):
        path = Path(root)
        phases = ['mounted_approach','dismount_hold','afoot_reversal','turn_complete'] if dismounted else [
            'mounted_approach','mounted_reversal','turn_complete']
        def box(x):
            return [[x-0.2,-0.2,0],[x-0.2,0.2,0],
                    [x+0.2,-0.2,0],[x+0.2,0.2,0]]
        rows = [{'frame':i*20,'time_s':float(i),
                 'operator_id':'operator-1','bicycle_id':'bike-1','sign_id':'sign-1',
                 'phase':phase,
                 'operator_body_vertices_m':box(2 if dismounted and phase in
                     ('afoot_reversal','turn_complete') else 0),
                 'bicycle_body_vertices_m':box(0)}
                for i,phase in enumerate(phases)]
        events = path/'phase-events.jsonl'
        events.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        (path/'video_frames.jsonl').write_text(''.join(json.dumps({
            'carla_frame':row['frame'],'time_s':row['time_s']})+'\n'
            for row in rows))
        authorization=path/'sign-authorization-source'
        authorization.write_text('fixture source; authorization unresolved')
        sign = path/'sign-inventory.json'
        sign.write_text(json.dumps({'message':'NO U TURN','erected':True,
                                    'sign_actor_id':'sign-1',
                                    'authorization_source_sha256':hashlib.sha256(
                                        authorization.read_bytes()).hexdigest()}))
        acquisition = {name:{'kind':'original_native','sha256':hashlib.sha256((path/name).read_bytes()).hexdigest()}
                       for name in analysis.REQUIRED}
        (path/'acquisition.json').write_text(json.dumps(acquisition))
        return path

    def test_dismounted_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            result = analysis.finalize(self.attempt(temp))
            self.assertTrue(result['dismounted_before_turn'])
            self.assertLess(result['dismount_time_s'],result['turn_start_s'])

    def test_mounted_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            result = analysis.finalize(self.attempt(temp,False))
            self.assertFalse(result['dismounted_before_turn'])
            self.assertIsNone(result['dismount_time_s'])

    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.attempt(temp)
            (path/'phase-events.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'missing or changed source'):
                analysis.finalize(path)

    def test_stale_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.attempt(temp)
            (path/'sign-inventory.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'missing or changed source'):
                analysis.finalize(path)

    def test_sign_authorization_binding_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.attempt(temp)
            sign=json.loads((path/'sign-inventory.json').read_text())
            sign['authorization_source_sha256']='a'*64
            (path/'sign-inventory.json').write_text(json.dumps(sign))
            acquisition=json.loads((path/'acquisition.json').read_text())
            acquisition['sign-inventory.json']['sha256']=hashlib.sha256(
                (path/'sign-inventory.json').read_bytes()).hexdigest()
            (path/'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError,'governing sign identity/authorization missing'):
                analysis.finalize(path)

    def test_frame_join_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.attempt(temp)
            frames=[json.loads(line) for line in (path/'video_frames.jsonl').read_text().splitlines()]
            frames[1]['carla_frame']+=1
            (path/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
            acquisition=json.loads((path/'acquisition.json').read_text())
            acquisition['video_frames.jsonl']['sha256']=hashlib.sha256(
                (path/'video_frames.jsonl').read_bytes()).hexdigest()
            (path/'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError,'original phase event/frame map join failed'):
                analysis.finalize(path)

    def test_phase_labels_without_body_separation_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.attempt(temp)
            rows=[json.loads(line) for line in (path/'phase-events.jsonl').read_text().splitlines()]
            rows[-2]['operator_body_vertices_m']=rows[-2]['bicycle_body_vertices_m']
            (path/'phase-events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            acquisition=json.loads((path/'acquisition.json').read_text())
            acquisition['phase-events.jsonl']['sha256']=hashlib.sha256(
                (path/'phase-events.jsonl').read_bytes()).hexdigest()
            (path/'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError,'afoot reversal lacks original body separation'):
                analysis.finalize(path)
