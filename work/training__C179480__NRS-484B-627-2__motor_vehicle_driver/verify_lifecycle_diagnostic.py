"""Exercise capture closure ordering with a fake world, never a CARLA claim."""
import importlib.util
import json
from pathlib import Path
import tempfile
import types

from capture_attempt import acquire_with_world_restore


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'c179480_capture_fakes', HERE/'tests'/'test_capture_attempt.py')
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)


def verify():
    events = []
    class World(fakes.FakeWorld):
        def apply_settings(self, value):
            super().apply_settings(value)
            if not value.synchronous_mode:
                events.append('restoration_verified')
    class Sink(fakes.MemorySink):
        closed = 0
        def close(self):
            super().close()
            Sink.closed += 1
            if Sink.closed == 4:
                events.append('encoders_closed')
    carla = types.SimpleNamespace(
        Location=lambda **kw: kw, Rotation=lambda **kw: kw,
        Transform=lambda *args: args,
        VehicleControl=lambda **kw: types.SimpleNamespace(**kw))
    world = World()
    samples = 0
    def sample(world, ego, follower):
        nonlocal samples
        samples += 1
        if samples == 3:
            events.append('capture_finished')
        return dict(ego_speed_mps=0.0, ego_on_roadway=True,
                    ego_lane_overlap=True, following_speed_mps=1.0,
                    following_gap_m=10.0)
    root = HERE.parents[1]/'.runtime-work'
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix='c179480-lifecycle-') as tmp:
        receipt = acquire_with_world_restore(
            world, carla, fakes.FakeVehicle(0), fakes.FakeVehicle(-12),
            fakes.FakeLibrary(), (15.0, 0.0), Path(tmp)/'attempt',
            frames=3, sample=sample, sink_factory=Sink)
        if receipt['source_frames'] != 3 or len(world.sensors) != 4:
            raise ValueError('Synthetic capture incomplete')
        if not all(sensor.destroyed for sensor in world.sensors):
            raise ValueError('Source camera ownership remains')
        if world.settings.synchronous_mode or world.settings.fixed_delta_seconds is not None:
            raise ValueError('World settings were not restored')
    # These three transitions are made only after the fake Native call returns,
    # its sensors are destroyed and all sinks are closed. They exercise the
    # ordering contract, not an operator attestation or actual process exit.
    events.append('native_exit')
    if Sink.closed != 4:
        raise ValueError('Encoder ownership remains')
    events.append('owner_released')
    events.append('saved_processing_started')
    expected = ['capture_finished','encoders_closed','restoration_verified',
                'native_exit','owner_released','saved_processing_started']
    if events != expected:
        raise ValueError('Capture lifecycle ordering differs: '+repr(events))
    return {'scope':'synthetic fake-world lifecycle', 'events':events,
            'source_cameras_closed':4, 'source_frames':3, 'exit_code':0,
            'actual_native_exit_claimed':False,
            'operator_release_claimed':False}


if __name__ == '__main__':
    print(json.dumps(verify(), sort_keys=True))
