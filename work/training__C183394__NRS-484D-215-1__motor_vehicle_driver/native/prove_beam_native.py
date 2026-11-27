"""CPU-test actual Native API calls and reject absent source readback."""
from types import SimpleNamespace as NS

from beam_native import command_tick, install


class Location:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Light:
    Position, LowBeam, HighBeam = 1, 2, 4

    def __new__(cls, bits):
        return int(bits)


class Actor:
    def __init__(self, position):
        self.position = position
        self.bits = 0
        self.controls = []
        self.destroyed = False

    def get_transform(self):
        return NS(location=self.position)

    def get_velocity(self):
        return NS(x=0, y=0)

    def set_light_state(self, bits):
        self.bits = bits

    def get_light_state(self):
        return self.bits

    def apply_control(self, control):
        self.controls.append(control)

    def destroy(self):
        self.destroyed = True


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class World:
    def __init__(self):
        self.settings = NS(synchronous_mode=False, fixed_delta_seconds=None)
        self.weather = None
        self.spawned = []
        self.bad_lane = False

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def set_weather(self, weather):
        self.weather = weather

    def get_map(self):
        return self

    def get_waypoint(self, point, project_to_road, lane_type):
        assert project_to_road is False
        if self.bad_lane:
            return NS(road_id=183394, lane_id=-1)
        return NS(road_id=183394, lane_id=-2 if lane_type == "shoulder" else 1)

    def get_blueprint_library(self):
        return self

    def find(self, name):
        assert name.startswith("vehicle.")
        return Blueprint()

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(transform.location)
        self.spawned.append((blueprint.attributes["role_name"], actor))
        return actor


class Client:
    def __init__(self):
        self.world = World()

    def generate_opendrive_world(self, source, parameters):
        assert "shoulder" in source and parameters.vertex_distance == .25
        return self.world


carla = NS(Location=Location, Rotation=lambda **kwargs: NS(**kwargs),
           Transform=lambda location, rotation: NS(location=location, rotation=rotation),
           OpendriveGenerationParameters=lambda **kwargs: NS(**kwargs),
           WeatherParameters=lambda **kwargs: NS(**kwargs),
           LaneType=NS(Shoulder="shoulder", Driving="driving"),
           VehicleLightState=Light, VehicleControl=lambda **kwargs: NS(**kwargs))

for case, expected in (("condition_a", "low_beam"), ("condition_b", "high_beam")):
    client = Client()
    scene = install(client, carla, case)
    assert client.world.settings.synchronous_mode
    assert client.world.settings.fixed_delta_seconds == .05
    assert client.world.weather.sun_altitude_angle == -30
    assert [role for role, _ in client.world.spawned] == ["c183394_ego", "c183394_oncoming"]
    assert command_tick(scene, carla)["requested_beam_state"] == "high_beam"
    scene["oncoming"].position.x = 0
    measured = command_tick(scene, carla)
    assert measured["requested_beam_state"] == expected
    assert measured["glare_or_lowermost_proven"] is False
    assert all(actor.controls for actor in scene["owned"])
    scene["ego"].bits = 0
    old = scene["ego"].set_light_state
    scene["ego"].set_light_state = lambda bits: None
    try:
        command_tick(scene, carla)
    except RuntimeError as error:
        assert "headlamp state readback" in str(error)
    else:
        raise AssertionError("missing original lamp readback accepted")
    scene["ego"].set_light_state = old
bad = Client()
bad.world.bad_lane = True
try:
    install(bad, carla, "condition_a")
except RuntimeError as error:
    assert "map readback" in str(error)
else:
    raise AssertionError("missing original shoulder lane accepted")
print("PASS: Native road, vehicle, lamp and control calls with source negatives")
