"""CPU contract probe for the frozen capture's Walker-specific API calls."""

import json
import sys
import types
from pathlib import Path

from walker_capture_adapter import adapt


class Actor:
    id = 17
    type_id = 'walker.pedestrian.test'

    def get_control(self):
        return types.SimpleNamespace(direction=types.SimpleNamespace(x=-1, y=0, z=0),
                                     speed=.4, jump=False)

    def get_velocity(self):
        return (-.4, 0, 0)


class World:
    def __init__(self, actor):
        self.actor = actor

    def get_actor(self, actor_id):
        return self.actor if actor_id == self.actor.id else None


class Client:
    def __init__(self, world):
        self.world = world

    def get_world(self):
        return self.world


def prove():
    package = types.ModuleType('carla_sgg')
    package.sgg = types.SimpleNamespace(copy_carla_vehicle_lights=lambda attributes, actor:
                                        attributes.update(vehicle_light_state=actor.get_light_state()))
    old = sys.modules.get('carla_sgg')
    sys.modules['carla_sgg'] = package
    try:
        original = Actor()
        client, ego = adapt(Client(World(original)), original)
        assert client.get_world().get_actor(17) is ego
        assert client.get_world().get_actor(18) is None
        assert ego.id == original.id and ego.get_velocity() == original.get_velocity()
        control = ego.get_control()
        assert all(getattr(control, name) is None for name in
                   ('throttle', 'steer', 'brake', 'hand_brake', 'reverse',
                    'manual_gear_shift', 'gear'))
        assert control.speed == .4 and control.direction.x == -1
        assert ego.is_at_traffic_light() is None
        lights = {}
        package.sgg.copy_carla_vehicle_lights(lights, ego)
        assert lights == {'vehicle_light_state': None, 'vehicle_lights_applicable': False}
        return {'format': 'worker-walker-adapter-cpu-proof', 'physical_actor_id': ego.id,
                'vehicle_only_fields': 'not_applicable_null', 'walker_speed_mps': control.speed,
                'graph_light_state': lights, 'original_actor_observed': False,
                'frozen_interface_calls_exercised': ['get_world', 'get_actor', 'get_control',
                                                     'is_at_traffic_light', 'copy_carla_vehicle_lights']}
    finally:
        if old is None:
            del sys.modules['carla_sgg']
        else:
            sys.modules['carla_sgg'] = old


if __name__ == '__main__':
    result = prove()
    Path(__file__).with_name('walker-adapter-proof.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
