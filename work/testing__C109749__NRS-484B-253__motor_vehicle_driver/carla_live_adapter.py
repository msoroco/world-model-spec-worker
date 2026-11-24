"""Live CARLA tick adapter for the sealed NRS 484B.253 acquisition.

The caller supplies already surveyed, spawned actors and four camera sensors.
All sensor queues must join the synchronous world tick; controller requests are
applied by an explicit callback, never substituted for observed controls.
"""

import io
import math
import queue

from PIL import Image

from left_turn_measurements import body_occupancy
from native_acquisition import CAMERAS
from native_source_review import review


class WorldLease:
    """Restore world state and destroy owned actors even after failed capture."""

    def __init__(self, world):
        self.world = world
        self.owned = []
        self.settings = None
        self.weather = None

    def __enter__(self):
        self.settings = self.world.get_settings()
        self.weather = self.world.get_weather()
        new = self.world.get_settings()
        new.synchronous_mode = True
        new.fixed_delta_seconds = 0.05
        self.world.apply_settings(new)
        return self

    def own(self, actor):
        if actor is None:
            raise ValueError("Native actor spawn failed")
        self.owned.append(actor)
        return actor

    def __exit__(self, exception_type, exception, traceback):
        for actor in reversed(self.owned):
            try:
                actor.destroy()
            except RuntimeError:
                pass
        self.world.apply_settings(self.settings)
        self.world.set_weather(self.weather)


def _vertices(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError("CARLA original body needs eight vertices")
    return [[float(v.x), float(v.y), float(v.z)] for v in vertices]


def _heading(actor):
    vector = actor.get_transform().get_forward_vector()
    return [float(vector.x), float(vector.y)]


def _png(image):
    if image is None or not isinstance(image.raw_data, (bytes, bytearray)):
        raise ValueError("original CARLA sensor image missing")
    size = (int(image.width), int(image.height))
    if min(size) <= 0 or len(image.raw_data) != size[0] * size[1] * 4:
        raise ValueError("original CARLA BGRA dimensions mismatch")
    rgb = Image.frombytes("RGBA", size, bytes(image.raw_data), "raw", "BGRA").convert("RGB")
    data = io.BytesIO()
    rgb.save(data, format="PNG")
    return data.getvalue()


class CarlaTickAdapter:
    def __init__(self, *, world, packet, ego, opponent, cameras, control_step,
                 location_factory, left_blinker_mask):
        if set(cameras) != set(CAMERAS):
            raise ValueError("four named Native camera sensors required")
        if ego.id == opponent.id:
            raise ValueError("opponent and subject actor identities alias")
        self.world = world
        self.packet = packet
        self.ego = ego
        self.opponent = opponent
        self.control_step = control_step
        self.left_blinker_mask = int(left_blinker_mask)
        self.attestation = review(packet, carla_map=world.get_map(),
                                  location_factory=location_factory)
        self.queues = {name: queue.Queue(maxsize=4) for name in CAMERAS}
        for name, sensor in cameras.items():
            sensor.listen(self.queues[name].put)
        self.initial_heading = _heading(ego)

    def source_attestation(self):
        return {"source_id": self.attestation["source_id"],
                "native_map_sha256": self.attestation["native_map_sha256"],
                "native_origin": True}

    def tick(self):
        self.control_step(self.ego, self.opponent)
        frame = int(self.world.tick())
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("Native world snapshot frame mismatch")
        pixels = {}
        for name in CAMERAS:
            image = self.queues[name].get(timeout=5)
            if image.frame != frame:
                raise ValueError("Native camera callback frame mismatch")
            pixels[name] = _png(image)
        e, o = _vertices(self.ego), _vertices(self.opponent)
        ego_control, other_control = self.ego.get_control(), self.opponent.get_control()
        ego_heading = _heading(self.ego)
        dot = sum(a * b for a, b in zip(ego_heading, self.initial_heading))
        turn_committed = dot < math.cos(math.radians(20))
        opponent_occupancy = body_occupancy(o, self.packet["intersection_polygon"])
        sample = {"ego_actor_id": self.ego.id, "opponent_actor_id": self.opponent.id,
                  "ego_driver_control_source": "original Native get_control",
                  "opponent_driver_control_source": "original Native get_control",
                  "ego_vertices": e, "opponent_vertices": o,
                  "ego_heading": ego_heading, "opponent_heading": _heading(self.opponent),
                  "ego_speed_mps": float(self.ego.get_velocity().length()),
                  "opponent_speed_mps": float(self.opponent.get_velocity().length()),
                  "ego_signal_left": bool(int(self.ego.get_light_state()) & self.left_blinker_mask),
                  "ego_turn_committed": turn_committed,
                  "opponent_cleared": not opponent_occupancy["any_vertex_inside"],
                  "ego_braking": float(ego_control.brake) > 0,
                  "ego_applied_control": {"throttle": float(ego_control.throttle),
                                          "brake": float(ego_control.brake),
                                          "steer": float(ego_control.steer)},
                  "opponent_applied_control": {"throttle": float(other_control.throttle),
                                               "brake": float(other_control.brake),
                                               "steer": float(other_control.steer)}}
        return frame, float(snapshot.timestamp.elapsed_seconds), sample, pixels
