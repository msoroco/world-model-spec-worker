import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest


folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(folder))
spec = importlib.util.spec_from_file_location('c179480_native_runner',
                                               folder / 'native_runner.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeLane:
    def __init__(self, lane_type, width):
        self.lane_type = lane_type
        self.lane_width = width
        self.road_id = 11
        self.lane_id = -1
        self.transform = types.SimpleNamespace(rotation=types.SimpleNamespace(yaw=0.0))

    def get_right_lane(self):
        return FakeLane('shoulder', 3.0)


class FakeMap:
    name = 'SurveyedTown'

    def get_waypoint(self, *_args, **_kwargs):
        return FakeLane('driving', 3.7)


class FakeActor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self):
        self.mapping = FakeMap()
        self.actors = []

    def get_map(self):
        return self.mapping

    def get_blueprint_library(self):
        return types.SimpleNamespace(find=lambda value: value)

    def try_spawn_actor(self, blueprint, transform):
        actor = FakeActor()
        self.actors.append(actor)
        return actor


class NativeRunnerTest(unittest.TestCase):
    def setUp(self):
        self.survey = dict(map_name='SurveyedTown',
                           anchor=dict(x=100.0, y=10.0, z=0.0, yaw=0.0),
                           lane_width_m=3.7, shoulder_width_m=3.0,
                           vehicle_width_m=1.9,
                           ego_blueprint='vehicle.ego',
                           following_blueprint='vehicle.following', frames=40)
        self.carla = types.SimpleNamespace(
            LaneType=types.SimpleNamespace(Driving='driving', Shoulder='shoulder'),
            Location=lambda **kw: types.SimpleNamespace(**kw),
            Rotation=lambda **kw: types.SimpleNamespace(**kw),
            Transform=lambda location, rotation: types.SimpleNamespace(
                location=location, rotation=rotation))

    def test_survey_places_blocking_and_clear_targets(self):
        road, _, _ = module.validate_survey(self.survey, FakeMap(), self.carla)
        blocked = module.placement(self.survey, road, self.carla, 'reference')
        clear = module.placement(self.survey, road, self.carla, 'contrast')
        self.assertEqual(blocked['stop_xy'], (100.0, 10.0))
        self.assertGreater(clear['stop_xy'][1], 10.0)
        self.assertEqual(blocked['following_spawn'].location.x,
                         clear['following_spawn'].location.x)
        self.assertTrue(blocked['target_lane_overlap'])
        self.assertFalse(clear['target_lane_overlap'])

    def test_three_fallbacks_preserve_pair_target_and_isolate_physical_risks(self):
        road, _, _ = module.validate_survey(self.survey, FakeMap(), self.carla)
        primary = module.placement(self.survey, road, self.carla, 'reference')
        observed = []
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            blocked = module.placement(self.survey, road, self.carla,
                                       'reference', candidate)
            clear = module.placement(self.survey, road, self.carla,
                                     'contrast', candidate)
            self.assertEqual(blocked['stop_xy'], primary['stop_xy'])
            self.assertEqual(blocked['ego_spawn'].location.x,
                             clear['ego_spawn'].location.x)
            self.assertEqual(blocked['following_spawn'].location.x,
                             clear['following_spawn'].location.x)
            self.assertEqual(blocked['tuning'], clear['tuning'])
            self.assertTrue(blocked['target_lane_overlap'])
            self.assertFalse(clear['target_lane_overlap'])
            self.assertIsNotNone(blocked['tuning'].risk_trigger)
            observed.append(blocked['tuning'].risk_trigger['metric'])
        self.assertEqual(len(set(observed)), 3)
        self.assertLess(module.placement(self.survey, road, self.carla,
                        'reference', 'fallback1')['ego_spawn'].location.x,
                        primary['ego_spawn'].location.x)
        self.assertLess(module.placement(self.survey, road, self.carla,
                        'reference', 'fallback2')['tuning'].approach_speed_mps,
                        primary['tuning'].approach_speed_mps)
        self.assertLess(module.placement(self.survey, road, self.carla,
                        'reference', 'fallback3')['following_spawn'].location.x,
                        primary['following_spawn'].location.x)
        with self.assertRaisesRegex(ValueError, 'Unknown physical-risk'):
            module.placement(self.survey, road, self.carla,
                             'reference', 'fallback4')

    def test_live_map_and_shoulder_must_match_survey(self):
        bad = dict(self.survey, map_name='OtherTown')
        with self.assertRaisesRegex(ValueError, 'Live map differs'):
            module.validate_survey(bad, FakeMap(), self.carla)
        bad = dict(self.survey, shoulder_width_m=4.0)
        with self.assertRaisesRegex(ValueError, 'shoulder differs'):
            module.validate_survey(bad, FakeMap(), self.carla)
        bad = dict(self.survey, anchor=dict(self.survey['anchor'], yaw=180.0))
        with self.assertRaisesRegex(ValueError, 'heading differs'):
            module.validate_survey(bad, FakeMap(), self.carla)

    def test_spawned_actors_are_destroyed_after_capture(self):
        world = FakeWorld()
        client = types.SimpleNamespace(get_world=lambda: world)
        original = module.acquire_with_world_restore
        try:
            def fake_capture(_world, _carla, ego, follower, _library,
                             stop_xy, attempt, **options):
                Path(attempt).mkdir()
                (Path(attempt)/'native-actors.jsonl').write_text(
                    json.dumps(dict(frame=101, ego_speed_mps=0.0,
                                    ego_on_roadway=True, ego_lane_overlap=True,
                                    following_speed_mps=1.0, following_gap_m=10.0))+'\n'+
                    json.dumps(dict(frame=102, ego_speed_mps=0.0,
                                    ego_on_roadway=True, ego_lane_overlap=True,
                                    following_speed_mps=0.5, following_gap_m=9.0))+'\n')
                (Path(attempt)/'video_frames.jsonl').write_text(
                    json.dumps(dict(video_frame=0, carla_frame=101, time_s=0.05))+'\n'+
                    json.dumps(dict(video_frame=1, carla_frame=102, time_s=0.10))+'\n')
                self.assertEqual(len(world.actors), 2)
                self.assertEqual(options['frames'], 40)
                self.assertEqual(options['follower_brake_gap_m'], 12.)
                return {'source_frames': 40, 'physical_completion_claimed': False}
            module.acquire_with_world_restore = fake_capture
            with tempfile.TemporaryDirectory() as tmp:
                result = module.run(client, self.carla, self.survey,
                                    Path(tmp)/'attempt', 'reference',
                                    candidate='fallback3')
                readback = json.loads((Path(tmp)/'attempt'/result['map_readback']).read_text())
                measured = json.loads((Path(tmp)/'attempt'/result['measurements']).read_text())
            self.assertEqual(readback['road_id'], 11)
            self.assertEqual(readback['candidate_id'], 'fallback3')
            self.assertEqual(measured['roadway_stop_frames'], [101, 102])
            self.assertEqual(len(measured['actor_source_sha256']), 64)
            self.assertFalse(readback['physical_completion_claimed'])
            self.assertTrue(all(actor.destroyed for actor in world.actors))
        finally:
            module.acquire_with_world_restore = original


if __name__ == '__main__':
    unittest.main()
