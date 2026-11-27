"""CPU construction and missing-source probes; no CARLA connection."""

import copy
from pathlib import Path
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from native.bus_scene import ZONE_KINDS, request, validate
from native.bus_construction import constructed_scene


class Blueprint:
    def set_attribute(self, *_):
        pass


class Actor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, road):
        self.road = road
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.actors = []

    def get_map(self):
        return SimpleNamespace(to_opendrive=lambda: self.road)

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda _: Blueprint(), filter=lambda _: [Blueprint()])

    def try_spawn_actor(self, *_):
        actor = Actor()
        self.actors.append(actor)
        return actor

    def spawn_actor(self, *_, **__):
        actor = Actor()
        self.actors.append(actor)
        return actor


class Client:
    def generate_opendrive_world(self, road):
        self.world = World(road)
        return self.world


carla = SimpleNamespace(Location=lambda **kw: kw, Rotation=lambda **kw: kw,
                        Transform=lambda *args: args)

for kind in ZONE_KINDS:
    scene = request(kind)
    assert validate(scene)["camera_count"] == 4
    client = Client()
    with constructed_scene(client, carla, scene) as actors:
        assert len(client.world.actors) == 6
        assert len(actors["cameras"]) == 4
        assert actors["designation_authority_confirmed"] is False
    assert all(actor.destroyed for actor in client.world.actors)
    assert not client.world.settings.synchronous_mode

for key, change, error in [
    ("camera", lambda scene: scene["cameras"].pop(), "four source cameras"),
    ("marker", lambda scene: scene.update(zone_id="wrong"), "loading-place marker"),
    ("rate", lambda scene: scene.update(rate_hz=10), "20 Hz duration"),
    ("claim", lambda scene: scene.update(actual_loading_confirmed=True), "claims observation"),
]:
    scene = copy.deepcopy(request("route_destination"))
    change(scene)
    try:
        validate(scene)
    except ValueError as exc:
        assert error in str(exc), (key, str(exc))
    else:
        raise AssertionError("missing rejection: " + key)

print("six bus-place construction variants and four source/claim negatives passed")
