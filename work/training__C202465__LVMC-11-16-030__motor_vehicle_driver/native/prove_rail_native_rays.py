"""CPU fake of Native call sequence, frame join and source rejection."""

from types import SimpleNamespace

from rail_native_rays import observe


class Location:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z

    def distance(self, other):
        return ((self.x-other.x)**2 + (self.y-other.y)**2 + (self.z-other.z)**2)**.5


class Transform:
    def __init__(self, location):
        self.location = location

    def transform(self, offset):
        return Location(self.location.x+offset.x, self.location.y+offset.y,
                        self.location.z+offset.z)


class Actor:
    def __init__(self, actor_id, y):
        self.id, self.type_id, self.is_alive = actor_id, "vehicle.fake_rail", True
        self.pose = Transform(Location(0, y, 0))
        self.bounding_box = SimpleNamespace(
            get_world_vertices=lambda pose: [
                Location(pose.location.x+.2*i, pose.location.y, 1.4) for i in range(8)],
            contains=lambda point, pose: False)

    def get_transform(self):
        return self.pose


class World:
    def __init__(self):
        self.calls = []

    def cast_ray(self, eye, target):
        self.calls.append((eye, target))
        if target.y < -50:
            return [SimpleNamespace(location=Location(-1, -10, 1.4), label="building")]
        return []


review = {"review_status": "independently_reviewed", "provenance_kind": "original_native",
          "crossing_kind": "at_grade", "source_sha256": "a"*64,
          "railway_identity": "reviewed original motor railway", "crossing_xyz_m": [0, 0, 0],
          "rail_unit_direction_xy": [0, 1],
          "rail_vehicle_lateral_tolerance_m": 1.5}
ego = Actor(1, 0)
ego.pose = Transform(Location(-30, 0, 0))
actors = [{"side": "left", "actor": Actor(2, -70)},
          {"side": "right", "actor": Actor(3, 70)}]
world = World()
row = observe(world, ego, actors, review, Location, 42)
assert row["frame"] == 42 and len(world.calls) >= 120
assert row["directions"]["left"]["clear_distance_m"] <= 50
assert row["directions"]["right"]["clear_distance_m"] == 121.92
assert not row["directions"]["left"]["rail_vehicle_visible_proxy"]
assert row["directions"]["right"]["rail_vehicle_visible_proxy"]


def reject(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


reject(lambda: observe(world, ego, actors, dict(review, review_status="schema_only"), Location, 42),
       "independently reviewed")
reject(lambda: observe(world, ego, actors[:1], review, Location, 42), "both directions")
reject(lambda: observe(world, ego, actors, dict(review, rail_unit_direction_xy=[1, 1]), Location, 42),
       "unit length")
reject(lambda: observe(world, ego, [actors[0], {"side": "right", "actor": Actor(4, -70)}],
                       review, Location, 42), "outside signed")
off_track = Actor(5, 70)
off_track.pose.location.x = 5
reject(lambda: observe(world, ego, [actors[0], {"side": "right", "actor": off_track}],
                       review, Location, 42), "off reviewed physical track")
print("PASS: Native world.cast_ray call path, source geometry and two traffic directions")
