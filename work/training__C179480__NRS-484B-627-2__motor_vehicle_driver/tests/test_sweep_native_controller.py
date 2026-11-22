"""Exercise Native sweep setpoints and light restoration without CARLA."""
from pathlib import Path
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import native_runner  # noqa: E402
from sweep_native_controller import controlled_phase  # noqa: E402
from test_native_runner import FakeWorld, NativeRunnerTest  # noqa: E402


class FakeLight:
    id = 501
    type_id = 'traffic.traffic_light'

    def __init__(self):
        self.state = 'Yellow'
        self.frozen = False

    def get_state(self):
        return self.state

    def set_state(self, state):
        self.state = state

    def freeze(self, frozen):
        self.frozen = frozen

    def is_frozen(self):
        return self.frozen


class SweepNativeControllerTests(unittest.TestCase):
    def setUp(self):
        base = NativeRunnerTest()
        base.setUp()
        self.survey = base.survey
        self.carla = base.carla
        self.carla.TrafficLightState = types.SimpleNamespace(Green='Green', Red='Red')

    def test_phase_changes_on_exact_ticks_and_restores(self):
        light = FakeLight()
        world = types.SimpleNamespace(tick=lambda: 100)
        with self.assertRaisesRegex(RuntimeError, 'capture failed'):
            with controlled_phase(world, light, self.carla, 9.0) as proxy:
                for _ in range(180):
                    proxy.tick()
                    self.assertEqual(light.get_state(), 'Green')
                proxy.tick()
                self.assertEqual(light.get_state(), 'Red')
                raise RuntimeError('capture failed')
        self.assertEqual((light.get_state(), light.is_frozen()), ('Yellow', False))
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            with controlled_phase(world, light, self.carla, 8.0):
                pass

    def test_runner_wires_three_sweep_axes(self):
        road, _, _ = native_runner.validate_survey(self.survey, FakeWorld().get_map(), self.carla)
        hazard = native_runner.placement(dict(self.survey, hazard_center_gap_m=6.0),
                                         road, self.carla, 'safe_operation_stop')
        self.assertEqual(hazard['hazard_spawn'].location.x, 106.0)
        with self.assertRaisesRegex(ValueError, 'Unreviewed hazard'):
            native_runner.placement(dict(self.survey, hazard_center_gap_m=5.0),
                                    road, self.carla, 'safe_operation_stop')
        world = FakeWorld()
        light = FakeLight()
        world.get_actors = lambda: types.SimpleNamespace(find=lambda ident: light if ident == 501 else None)
        client = types.SimpleNamespace(get_world=lambda: world)
        original = native_runner.acquire_with_world_restore
        try:
            def inspect_capture(capture_world, _carla, _ego, _follower,
                                _library, _stop, _attempt, **options):
                self.assertIs(capture_world.world, world)
                self.assertEqual(light.get_state(), 'Yellow')
                self.assertTrue(light.is_frozen())
                self.assertEqual(options['follower_brake_gap_m'], 7.0)
                raise RuntimeError('capture failed')
            native_runner.acquire_with_world_restore = inspect_capture
            with tempfile.TemporaryDirectory(dir=HERE.parents[1]/'.runtime-work') as tmp:
                with self.assertRaisesRegex(RuntimeError, 'capture failed'):
                    native_runner.run(client, self.carla,
                                      dict(self.survey, governing_traffic_light_id=501,
                                           governing_red_onset_s=11.0),
                                      Path(tmp)/'attempt', 'law_required_stop')
            self.assertEqual((light.get_state(), light.is_frozen()), ('Yellow', False))
            self.assertTrue(all(actor.destroyed for actor in world.actors))
            def inspect_follower(capture_world, _carla, _ego, _follower,
                                 _library, _stop, _attempt, **options):
                self.assertIs(capture_world, world)
                self.assertEqual(options['follower_brake_gap_m'], 9.5)
                raise RuntimeError('capture failed')
            native_runner.acquire_with_world_restore = inspect_follower
            with tempfile.TemporaryDirectory(dir=HERE.parents[1]/'.runtime-work') as tmp:
                with self.assertRaisesRegex(RuntimeError, 'capture failed'):
                    native_runner.run(client, self.carla,
                                      dict(self.survey, following_gap_m=9.5),
                                      Path(tmp)/'attempt', 'reference')
            with self.assertRaisesRegex(ValueError, 'Unreviewed governing'):
                native_runner.run(client, self.carla,
                                  dict(self.survey, governing_traffic_light_id=501,
                                       governing_red_onset_s=12.0),
                                  Path(tmp)/'attempt', 'law_required_stop')
        finally:
            native_runner.acquire_with_world_restore = original


if __name__ == '__main__':
    unittest.main()
