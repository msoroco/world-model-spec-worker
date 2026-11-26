"""Fake-client construction tests; no CARLA process or physical evidence."""

from copy import deepcopy
from dataclasses import dataclass

from native_construction import constructed_scene
from stop_yield_scene import CASES, request


@dataclass
class Location:
    x: float
    y: float
    z: float


@dataclass
class Rotation:
    pitch: float
    yaw: float
    roll: float


@dataclass
class Transform:
    location: Location
    rotation: Rotation


class Carla:
    Location = Location
    Rotation = Rotation
    Transform = Transform


class Blueprint:
    def __init__(self, ident):
        self.id = ident
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Library:
    def find(self, ident):
        return Blueprint(ident)

    def filter(self, pattern):
        return [Blueprint("walker.pedestrian.0001")] if pattern == "walker.pedestrian.*" else []


class Actor:
    def __init__(self, blueprint, pose):
        self.blueprint = blueprint
        self.pose = pose
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class Settings:
    synchronous_mode = False
    fixed_delta_seconds = None


class Map:
    def __init__(self, xodr):
        self.xodr = xodr

    def to_opendrive(self):
        return self.xodr


class World:
    def __init__(self, xodr, fail_spawn=None):
        self.map = Map(xodr)
        self.settings = Settings()
        self.library = Library()
        self.actors = []
        self.fail_spawn = fail_spawn

    def get_map(self):
        return self.map

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_blueprint_library(self):
        return self.library

    def try_spawn_actor(self, blueprint, pose):
        if blueprint.id == self.fail_spawn:
            return None
        actor = Actor(blueprint, pose)
        self.actors.append(actor)
        return actor

    def spawn_actor(self, blueprint, pose, attach_to=None):
        actor = self.try_spawn_actor(blueprint, pose)
        if actor is not None:
            actor.attach_to = attach_to
        return actor


class Client:
    def __init__(self, fail_spawn=None, lose_sign=False, lose_signal=False,
                 move_sign=False, move_reference=False):
        self.fail_spawn = fail_spawn
        self.lose_sign = lose_sign
        self.lose_signal = lose_signal
        self.move_sign = move_sign
        self.move_reference = move_reference
        self.world = None

    def generate_opendrive_world(self, xodr):
        if self.lose_sign:
            xodr = xodr.replace('id="stop-111325"', 'id="missing"')
        if self.lose_signal:
            xodr = xodr.replace('id="traffic-signal-111325"', 'id="missing"')
        if self.move_sign:
            xodr = xodr.replace('id="stop-111325" s="74"', 'id="stop-111325" s="60"')
        if self.move_reference:
            xodr = xodr.replace('id="line-111325" name="marked-stop-line" type="roadMark" s="74"',
                                'id="line-111325" name="marked-stop-line" type="roadMark" s="60"')
        self.world = World(xodr, self.fail_spawn)
        return self.world


def rejects(scene, client, fragment):
    try:
        with constructed_scene(client, Carla, scene):
            pass
    except (ValueError, RuntimeError) as error:
        if fragment not in str(error):
            raise AssertionError(str(error)) from error
        if client.world is not None:
            assert not client.world.settings.synchronous_mode
            assert client.world.settings.fixed_delta_seconds is None
            assert all(actor.destroyed for actor in client.world.actors)
        return
    raise AssertionError("Invalid Native construction passed")


def main():
    for slug in sorted(CASES):
        scene = request(slug)
        client = Client()
        with constructed_scene(client, Carla, scene) as built:
            assert len(built["cameras"]) == 4 and built["ego"] is not built["through"]
            assert built["world"].settings.synchronous_mode
            assert abs(built["world"].settings.fixed_delta_seconds - .05) < 1e-6
            if slug == "police_directed_control":
                assert built["officer"] is not None
            else:
                assert built["officer"] is None
        assert not client.world.settings.synchronous_mode
        assert client.world.settings.fixed_delta_seconds is None
        assert all(actor.destroyed for actor in client.world.actors)
    rejects(request("complete_stop_then_yield"), Client(lose_sign=True), "omitted governing sign")
    rejects(request("complete_stop_then_yield"), Client(fail_spawn="vehicle.tesla.model3"), "subject spawn failed")
    rejects(request("complete_stop_then_yield"), Client(fail_spawn="sensor.camera.rgb"), "source camera spawn failed")
    rejects(request("police_directed_control"), Client(fail_spawn="walker.pedestrian.0001"), "officer actor spawn failed")
    rejects(request("signal_directed_control"), Client(lose_signal=True), "omitted controlling traffic signal")
    rejects(request("complete_stop_then_yield"), Client(move_sign=True), "changed governing sign station")
    rejects(request("complete_stop_then_yield"), Client(move_reference=True), "changed stopping-reference geometry")
    print("12 fake-CARLA constructions, cleanup and seven missing-source/geometry/spawn negatives passed; no simulator started")


if __name__ == "__main__":
    main()
