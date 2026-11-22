"""Source-visible light phase control for the C179480 Native sweep.

The wrapper changes only the surveyed light, before each synchronous world tick.
The original state and frozen flag are restored even if capture fails.
"""
from contextlib import contextmanager

RED_ONSETS_S = (9.0, 11.0, 13.0)


class PhaseWorld:
    def __init__(self, world, light, carla, red_onset_s):
        if red_onset_s not in RED_ONSETS_S:
            raise ValueError('Unreviewed governing red-onset setting')
        if not all(hasattr(light, name) for name in ('get_state', 'set_state', 'freeze', 'is_frozen')):
            raise ValueError('Surveyed light lacks state/freeze readback')
        self.world = world
        self.light = light
        self.green = carla.TrafficLightState.Green
        self.red = carla.TrafficLightState.Red
        self.red_onset_sample = round(red_onset_s * 20)
        self.sample = 0

    def __getattr__(self, name):
        return getattr(self.world, name)

    def tick(self, *args, **kwargs):
        wanted = self.green if self.sample < self.red_onset_sample else self.red
        self.light.set_state(wanted)
        frame = self.world.tick(*args, **kwargs)
        if self.light.get_state() != wanted:
            raise ValueError('Surveyed light did not retain requested state')
        self.sample += 1
        return frame


@contextmanager
def controlled_phase(world, light, carla, red_onset_s):
    if red_onset_s is None:
        yield world
        return
    proxy = PhaseWorld(world, light, carla, red_onset_s)
    original_state = light.get_state()
    original_frozen = light.is_frozen()
    try:
        light.freeze(True)
        if not light.is_frozen():
            raise ValueError('Surveyed light did not freeze for phase control')
        yield proxy
    finally:
        light.set_state(original_state)
        light.freeze(original_frozen)
        if light.get_state() != original_state or light.is_frozen() != original_frozen:
            raise ValueError('Surveyed light state/freeze restoration failed')
