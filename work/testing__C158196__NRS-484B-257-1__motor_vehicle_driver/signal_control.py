"""Native traffic-light selection and reversible state control for C158196.

This controls a real CARLA signal actor; callers must separately retain image
evidence that its vehicular heads are installed and uncovered. A frozen phase is
not, by itself, evidence of an inoperative signal.
"""

from contextlib import contextmanager
import json
import math
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


class SignalSourceWriter:
    """Append original same-tick signal, body and four-camera identities.

    The caller owns camera encoding and passes original CARLA sensor packets.
    This writer never repairs a missing sensor frame or infers signal control
    from an image. The saved video producer must use the same packet order.
    """

    def __init__(self, root, context):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.context = dict(context)
        required = ("native_map_id", "intersection_id", "ego_road_id", "ego_lane_id",
                    "native_signal_id", "affected_lane_source", "signal_head_video_source",
                    "signed_entrance_source", "junction_source", "intersection_polygon_xy_m")
        if any(self.context.get(key) is None for key in required):
            raise ValueError("Incomplete original signal context")
        self.paths = [self.root / name for name in
                      ("signal_context.json", "signal_history.jsonl", "video_frames.jsonl")]
        if any(path.exists() for path in self.paths):
            raise ValueError("Original signal source already exists")
        self.paths[0].write_text(json.dumps(self.context, sort_keys=True, allow_nan=False) + "\n")
        self.count = 0
        self.previous = None

    def add_tick(self, world, ego, light, camera_packets, expected_controls_ego):
        if type(expected_controls_ego) is not bool:
            raise ValueError("Expected Native lane governance is required")
        if not isinstance(camera_packets, dict) or set(camera_packets) != set(CAMERAS):
            raise ValueError("Four named original camera packets required")
        snapshot = world.get_snapshot()
        frame = snapshot.frame
        time_s = _finite(snapshot.timestamp.elapsed_seconds, "Native timestamp")
        if type(frame) is not int or frame < 0 or (self.previous and
                (frame <= self.previous[0] or time_s <= self.previous[1])):
            raise ValueError("Nonmonotone Native frame")
        for name in CAMERAS:
            packet = camera_packets[name]
            if packet.frame != frame or abs(_finite(packet.timestamp, name + " timestamp") - time_s) > 1e-3:
                raise ValueError("Camera frame or timestamp differs from Native tick: " + name)
            if (type(packet.width) is not int or type(packet.height) is not int or
                    packet.width <= 0 or packet.height <= 0 or
                    len(packet.raw_data) != packet.width * packet.height * 4):
                raise ValueError("Missing original camera pixels: " + name)
        native_map = world.get_map()
        if native_map.name != self.context["native_map_id"] or light.id != self.context["native_signal_id"]:
            raise ValueError("Original map or signal identity changed")
        transform = ego.get_transform()
        waypoint = native_map.get_waypoint(transform.location, project_to_road=False)
        if waypoint is None or [waypoint.road_id, waypoint.lane_id] != [
                self.context["ego_road_id"], self.context["ego_lane_id"]]:
            raise ValueError("Ego left sourced signal approach")
        governed = {(wp.road_id, wp.lane_id) for wp in light.get_affected_lane_waypoints()}
        controls = (waypoint.road_id, waypoint.lane_id) in governed
        if controls is not expected_controls_ego:
            raise ValueError("Native signal governance changed during capture")
        state = str(light.get_state()).split(".")[-1]
        if state not in ("Red", "Yellow", "Green", "Off"):
            raise ValueError("Unsupported original signal indication")
        vertices = ego.bounding_box.get_world_vertices(transform)
        if len(vertices) < 4:
            raise ValueError("Incomplete original ego body")
        body = [[_finite(vertex.x, "body x"), _finite(vertex.y, "body y")]
                for vertex in vertices]
        velocity = ego.get_velocity()
        speed = math.sqrt(sum(_finite(getattr(velocity, axis), "ego velocity")**2
                              for axis in ("x", "y", "z")))
        if world.get_snapshot().frame != frame:
            raise ValueError("World advanced during source observation")
        row = {"frame": frame, "time_s": time_s, "native_signal_id": light.id,
               "ego_road_id": waypoint.road_id, "ego_lane_id": waypoint.lane_id,
               "signal_state": state, "signal_controls_ego": controls,
               "ego_speed_mps": speed, "ego_body_vertices_xy_m": body}
        frame_row = {"video_frame": self.count, "carla_frame": frame,
                     "time_s": time_s,
                     "camera_frames": {name: camera_packets[name].frame for name in CAMERAS}}
        for path, value in zip(self.paths[1:], (row, frame_row)):
            with path.open("a") as handle:
                handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        self.previous = (frame, time_s)
        self.count += 1
        return row, frame_row


def find_governing_signal(world, road_id, lane_id):
    """Choose only a signal whose affected Native waypoint matches the approach."""
    matches = []
    for light in world.get_actors().filter("traffic.traffic_light*"):
        affected = light.get_affected_lane_waypoints()
        if any(wp.road_id == road_id and wp.lane_id == lane_id for wp in affected):
            matches.append(light)
    if len(matches) != 1:
        raise ValueError(f"Expected one governing traffic light, found {len(matches)}")
    return matches[0]


class SignalControl:
    """Apply a requested Native signal state and restore the actor afterward."""

    def __init__(self, world, light, states, target):
        if target not in ("Red", "Green", "Off"):
            raise ValueError("Unsupported target state")
        self.world, self.light, self.states, self.target = world, light, states, target
        self.original = None

    def __enter__(self):
        self.original = self.light.get_state()
        self.light.freeze(True)
        try:
            self.light.set_state(getattr(self.states, self.target))
            self.world.tick()
            if self.light.get_state() != getattr(self.states, self.target):
                raise ValueError("Traffic light state readback failed")
        except Exception:
            self.light.set_state(self.original)
            self.light.freeze(False)
            raise
        return self.light

    def __exit__(self, *_):
        self.light.set_state(self.original)
        self.light.freeze(False)
        self.world.tick()
        if self.light.get_state() != self.original:
            raise ValueError("Traffic light restoration readback failed")


@contextmanager
def construct_signal_comparison(world, site, blueprints, transforms, states,
                                target_state, signal_id, expected_controls_ego):
    """Spawn an ego/through pair and read back the selected signal's lane control.

    A selected head can govern the ego entrance or another entrance. This
    construction verifies Native lane relationships; sign propriety, head
    visibility and legal control remain separate source-review questions.
    """
    native_map = world.get_map()
    if native_map.name != site.get("native_map_id"):
        raise ValueError("Native map differs from selected signed intersection")
    lanes = site.get("approach_lanes")
    if (not isinstance(lanes, dict) or set(lanes) != {"ego", "through"} or
            any(not isinstance(lanes[role], list) or len(lanes[role]) != 2 or
                any(type(v) is not int for v in lanes[role]) for role in lanes) or
            lanes["ego"] == lanes["through"]):
        raise ValueError("Two distinct sourced approach lanes required")
    if (set(blueprints) != {"ego", "through"} or
            set(transforms) != {"ego", "through"} or
            type(signal_id) is not int or signal_id <= 0 or
            type(expected_controls_ego) is not bool):
        raise ValueError("Exact actor and signal construction inputs required")
    owned = []
    try:
        actors = {}
        for role in ("ego", "through"):
            actor = world.try_spawn_actor(blueprints[role], transforms[role])
            if actor is None:
                raise ValueError("Native vehicle spawn failed: " + role)
            owned.append(actor)
            waypoint = native_map.get_waypoint(actor.get_location(), project_to_road=False)
            if (waypoint is None or
                    [int(waypoint.road_id), int(waypoint.lane_id)] != lanes[role]):
                raise ValueError("Native vehicle outside selected approach lane: " + role)
            actors[role] = actor
        lights = [light for light in world.get_actors().filter("traffic.traffic_light*")
                  if light.id == signal_id]
        if len(lights) != 1:
            raise ValueError("Exact selected Native signal actor required")
        light = lights[0]
        governed = {(int(wp.road_id), int(wp.lane_id))
                    for wp in light.get_affected_lane_waypoints()}
        controls_ego = tuple(lanes["ego"]) in governed
        if controls_ego is not expected_controls_ego:
            raise ValueError("Selected signal governance differs from comparison case")
        with SignalControl(world, light, states, target_state):
            yield {"actors": actors, "signal": light,
                   "signal_controls_ego": controls_ego,
                   "physical_head_visibility_verified": False,
                   "legal_exception_verified": False}
    finally:
        for actor in reversed(owned):
            actor.destroy()
