"""CPU runner wiring tests; acquisition and processing are test doubles."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from native_runner import run

HERE = Path(__file__).resolve().parent


def fixture():
    survey = json.loads((HERE/'draft-fire-lane-survey.json').read_text())
    survey['map_name'] = 'TownFireLane'
    return survey


def environment(*, wrong_following_road=False):
    def location(x, y, z=0):
        return SimpleNamespace(x=x, y=y, z=z)
    sign = SimpleNamespace(id=101, type_id='static.prop.fire_lane_sign',
        get_transform=lambda: SimpleNamespace(location=location(6, -1)))
    def waypoint(xy, **kwargs):
        road = 19 if wrong_following_road and xy.x < 0 else 17
        return SimpleNamespace(road_id=road, lane_id=-1,
            transform=SimpleNamespace(location=location(xy.x, xy.y)))
    mapping = SimpleNamespace(name='TownFireLane', get_waypoint=waypoint)
    spawned = []
    def spawn(blueprint, transform):
        actor = SimpleNamespace(destroy=lambda: spawned.append('destroy'))
        spawned.append(blueprint)
        return actor
    world = SimpleNamespace(get_map=lambda: mapping,
        get_actors=lambda: SimpleNamespace(find=lambda ident: sign if ident == 101 else None),
        get_blueprint_library=lambda: SimpleNamespace(find=lambda name: name),
        try_spawn_actor=spawn)
    carla = SimpleNamespace(
        Location=lambda **kwargs: SimpleNamespace(**kwargs),
        Rotation=lambda **kwargs: SimpleNamespace(**kwargs),
        Transform=lambda loc, rot: SimpleNamespace(location=loc, rotation=rot),
        LaneType=SimpleNamespace(Driving=1))
    return SimpleNamespace(get_world=lambda: world), carla, spawned


class RunnerTests(unittest.TestCase):
    def test_runner_binds_survey_vehicles_and_measurement(self):
        client, carla, spawned = environment()
        def acquisition(world, carla, ego, follower, sign, plan, case, attempt):
            self.assertEqual(case, 'reference')
            self.assertEqual(plan['fixed_context']['road_id'], 17)
            return {'source_frames': 600, 'physical_completion_claimed': False}
        def processor(attempt, case):
            return {'case': case, 'physical_or_legal_completion_claimed': False}
        with tempfile.TemporaryDirectory() as tmp:
            result = run(client, carla, fixture(), 'reference', Path(tmp)/'attempt',
                         acquisition=acquisition, processor=processor)
            self.assertEqual(result['case'], 'reference')
            self.assertTrue((Path(tmp)/'attempt/native-survey-readback.json').is_file())
            self.assertTrue((Path(tmp)/'attempt/source-measurement.json').is_file())
            provenance = json.loads((Path(tmp)/'attempt/acquisition-provenance.json').read_text())
            self.assertEqual(provenance['provenance_kind'], 'native')
            self.assertFalse(provenance['diagnostic_fixture'])
        self.assertEqual(spawned[-2:], ['destroy', 'destroy'])

    def test_different_following_road_rejected_before_spawn(self):
        client, carla, spawned = environment(wrong_following_road=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'following spawn differs'):
                run(client, carla, fixture(), 'reference', Path(tmp)/'attempt')
        self.assertEqual(spawned, [])

    def test_prior_attempt_preserved(self):
        client, carla, spawned = environment()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'attempt'
            path.mkdir()
            (path/'sentinel').write_text('retained')
            with self.assertRaisesRegex(ValueError, 'Retain previous attempt'):
                run(client, carla, fixture(), 'reference', path)
            self.assertEqual((path/'sentinel').read_text(), 'retained')
        self.assertEqual(spawned, [])

    def test_materialized_bundle_directory_is_accepted(self):
        client, carla, spawned = environment()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'attempt'
            path.mkdir()
            (path/'config.json').write_text('{}')
            (path/'runner.py').write_text('')
            (path/'construction.json').write_text(json.dumps({
                'files': [{'path': 'runner.py'}, {'path': 'config.json'}]}))
            result = run(client, carla, fixture(), 'reference', path,
                         acquisition=lambda *args: {
                             'source_frames': 600, 'restoration_verified': True},
                         processor=lambda *args: {
                             'physical_or_legal_completion_claimed': False})
            self.assertEqual(result['capture']['source_frames'], 600)
            self.assertTrue((path/'native-survey-readback.json').is_file())
        self.assertEqual(spawned[-2:], ['destroy', 'destroy'])


if __name__ == '__main__':
    unittest.main()
