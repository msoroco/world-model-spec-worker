"""CPU proof of the Native qualifier acquisition calls and source shapes."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from qualifier_context import (device_row, find_device, spawn_traffic_actor,
                               traffic_command, traffic_row, write_context_manifest)
from qualifier_runner import check, control_for
from qualifier_geometry import open_drive


class Actor:
    id = 22
    type_id = 'vehicle.test'
    bounding_box = SimpleNamespace(extent=SimpleNamespace(x=2.1, y=.9))

    def __init__(self, x=-16, y=-1.75):
        self.location = SimpleNamespace(x=x, y=y, z=8.8)
        self.commands = []

    def get_transform(self):
        return SimpleNamespace(location=self.location,
                               rotation=SimpleNamespace(yaw=0))

    def get_velocity(self):
        return SimpleNamespace(x=1.0, y=0.0, z=0.0)

    def apply_control(self, value):
        self.commands.append(value)


class Blueprint:
    def __init__(self, name):
        self.id = name
        self.role = None

    def set_attribute(self, name, value):
        if name != 'role_name':
            raise ValueError(name)
        self.role = value


class World:
    def __init__(self):
        self.blueprints = [Blueprint('vehicle.a'), Blueprint('vehicle.b')]
        self.actors = []
        self.spawned = None

    def get_blueprint_library(self):
        return SimpleNamespace(filter=lambda pattern: self.blueprints)

    def spawn_actor(self, blueprint, transform):
        self.spawned = (blueprint, transform)
        return Actor(transform.location.x, transform.location.y)

    def get_actors(self):
        return SimpleNamespace(filter=lambda pattern: self.actors)


def main():
    result = check()
    assert result['passed'] and len(result['targets']) == 4
    assert 'proposed-crosswalk-traffic-light' in open_drive('device_direction_near')
    world = World()
    carla = SimpleNamespace(Location=lambda **kw: SimpleNamespace(**kw),
        Rotation=lambda **kw: SimpleNamespace(**kw),
        Transform=lambda location, rotation: SimpleNamespace(location=location, rotation=rotation),
        VehicleControl=lambda **kw: kw)
    owned = []
    actor = spawn_traffic_actor(world, carla, owned)
    assert len(owned) == 1 and world.spawned[0].role == 'c229397_traffic_context'
    assert world.spawned[1].location.x == -16 and world.spawned[1].location.y == -1.75
    command = traffic_command(actor, 10, carla)
    row = traffic_row(actor, 10, 710, .5, command)
    assert row['actor_id'] == 22 and row['native_frame'] == 710 and len(actor.commands) == 1
    assert traffic_command(actor, 300, carla)['brake'] == .7
    assert find_device(world) is None
    absent = device_row(None, 10, 710, .5)
    assert absent['device_present'] is False and absent['state'] is None
    device = Actor(1, -2)
    device.type_id = 'traffic.traffic_light'
    device.get_state = lambda: 'Green'
    world.actors.append(device)
    assert find_device(world) is device
    present = device_row(device, 10, 710, .5)
    assert present['device_id'] == 22 and present['state'] == 'Green'
    assert control_for('traffic_conflict_near', 300, 1, 0)['hand_brake']
    print(json.dumps({'passed': True, 'qualifier_cases': list(result['targets']),
        'second_actor_spawn_call': True, 'traffic_control_and_row': True,
        'device_present_and_absent_rows': True, 'legal_verdict_claimed': False},
        sort_keys=True))


if __name__ == '__main__':
    main()
