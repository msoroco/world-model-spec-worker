"""Native traffic-light selection and reversible state control for C158196.

This controls a real CARLA signal actor; callers must separately retain image
evidence that its vehicular heads are installed and uncovered. A frozen phase is
not, by itself, evidence of an inoperative signal.
"""

from contextlib import contextmanager
import json
import math
from pathlib import Path
import subprocess
from queue import Empty, Queue


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERA_SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
                "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


class FourCameraEncoder:
    """Retain four original BGRA sensor streams in lossless FFV1 containers."""

    def __init__(self, root, sizes=None, fps=20):
        self.root = Path(root)
        self.sizes = dict(CAMERA_SIZES if sizes is None else sizes)
        if set(self.sizes) != set(CAMERAS) or type(fps) is not int or fps <= 0:
            raise ValueError("Four named camera dimensions and integer rate required")
        if any(not isinstance(size, (tuple, list)) or len(size) != 2 or
               any(type(v) is not int or v <= 0 for v in size)
               for size in self.sizes.values()):
            raise ValueError("Invalid camera dimensions")
        self.fps = fps
        self.processes = {}
        self.count = 0

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        if any((self.root / (name + ".mkv")).exists() for name in CAMERAS):
            raise ValueError("Original camera video already exists")
        try:
            for name in CAMERAS:
                width, height = self.sizes[name]
                command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                           "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                           f"{width}x{height}", "-framerate", str(self.fps),
                           "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "3",
                           "-pix_fmt", "bgr0", str(self.root / (name + ".mkv"))]
                self.processes[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                        stdout=subprocess.DEVNULL,
                                                        stderr=subprocess.PIPE)
        except Exception:
            self._finish(abort=True)
            raise
        return self

    def validate_packets(self, packets):
        if set(packets) != set(CAMERAS):
            raise ValueError("Four original camera packets required")
        for name in CAMERAS:
            packet = packets[name]
            width, height = self.sizes[name]
            if (packet.width, packet.height) != (width, height) or len(packet.raw_data) != width * height * 4:
                raise ValueError("Camera pixels differ from capture profile: " + name)

    def add_packets(self, packets):
        self.validate_packets(packets)
        for name in CAMERAS:
            self.processes[name].stdin.write(packets[name].raw_data)
        self.count += 1

    def _finish(self, abort=False):
        failures = []
        processes, self.processes = self.processes, {}
        for name, process in processes.items():
            if abort:
                if process.poll() is None:
                    process.kill()
            process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace")
            process.stderr.close()
            code = process.wait()
            if not abort and (code != 0 or not (self.root / (name + ".mkv")).is_file()):
                failures.append(name + ": " + stderr[-400:])
        if failures:
            raise ValueError("Four-camera FFV1 encoding failed: " + "; ".join(failures))

    def __exit__(self, kind, value, trace):
        self._finish(abort=kind is not None)
        return False


class NativeSignalCapture:
    """Own four Native RGB sensors and capture the selected case per world tick.

    The caller supplies exact camera blueprints/mounts and drives the vehicles
    before each tick. An exception invalidates the attempt; raw source rows and
    videos are never silently repaired or reused as a successful capture.
    """

    def __init__(self, world, root, actors, light, context, expected_controls_ego,
                 camera_blueprints, camera_mounts, client, case_id, required_atoms,
                 sizes=None, sensor_timeout_s=10, capture_factory=None):
        self.world, self.root, self.actors, self.light = world, Path(root), actors, light
        self.context, self.expected_controls_ego = context, expected_controls_ego
        self.camera_blueprints, self.camera_mounts = camera_blueprints, camera_mounts
        self.client, self.case_id, self.required_atoms = client, case_id, required_atoms
        self.capture_factory = capture_factory
        if not client or not isinstance(case_id, str) or not case_id or not isinstance(required_atoms, (list, tuple)):
            raise ValueError("Original PipelineCapture identity and Core atoms required")
        self.sizes = sizes
        self.sensor_timeout_s = _finite(sensor_timeout_s, "sensor timeout")
        if (not isinstance(actors, dict) or set(actors) != {"ego", "through"} or
                set(camera_blueprints) != set(CAMERAS) or set(camera_mounts) != set(CAMERAS)):
            raise ValueError("Exact actor pair and four camera mounts required")
        self.sensors = {}
        self.queues = {}
        self.encoder = None
        self.writer = None
        self.pipeline_capture = None

    def __enter__(self):
        try:
            for name in CAMERAS:
                mount = self.camera_mounts[name]
                if not isinstance(mount, dict) or set(mount) != {"transform", "attach_to"}:
                    raise ValueError("Camera mount needs exact transform and attachment: " + name)
                role = mount["attach_to"]
                if role not in (None, "ego", "through"):
                    raise ValueError("Unknown camera attachment: " + name)
                options = {} if role is None else {"attach_to": self.actors[role]}
                sensor = self.world.spawn_actor(self.camera_blueprints[name],
                                                mount["transform"], **options)
                if sensor is None:
                    raise ValueError("Native camera spawn failed: " + name)
                self.sensors[name] = sensor
                queue = Queue()
                self.queues[name] = queue
                sensor.listen(queue.put)
            self.encoder = FourCameraEncoder(self.root, self.sizes)
            self.encoder.__enter__()
            if self.capture_factory is None:
                from pipeline_capture import PipelineCapture
                self.capture_factory = PipelineCapture
            self.pipeline_capture = self.capture_factory(
                self.client, self.actors["ego"], self.root, self.case_id,
                required_observations=self.required_atoms)
            self.writer = SignalSourceWriter(self.root, self.context)
            return self
        except Exception:
            self._close(True)
            raise

    def capture_tick(self):
        frame = self.world.tick()
        if type(frame) is not int:
            raise ValueError("Native tick did not return a frame identity")
        packets = {}
        for name in CAMERAS:
            try:
                packet = self.queues[name].get(timeout=self.sensor_timeout_s)
            except Empty as exc:
                raise ValueError("Missing original camera frame: " + name) from exc
            if packet.frame != frame:
                raise ValueError("Stale or future original camera frame: " + name)
            packets[name] = packet
        self.encoder.validate_packets(packets)
        observation = self.writer.add_tick(self.world, self.actors["ego"], self.light,
                                           packets, self.expected_controls_ego,
                                           through=self.actors["through"])
        self.encoder.add_packets(packets)
        self.pipeline_capture.capture(frame, observation[0]["time_s"])
        return observation

    def _close(self, abort):
        try:
            if self.pipeline_capture is not None:
                self.pipeline_capture.close(confirmed=not abort)
        finally:
            try:
                for sensor in reversed(list(self.sensors.values())):
                    try:
                        sensor.stop()
                    finally:
                        sensor.destroy()
            finally:
                if self.encoder is not None and self.encoder.processes:
                    self.encoder._finish(abort=abort)

    def __exit__(self, kind, value, trace):
        self._close(abort=kind is not None)
        return False


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
                    "signed_entrance_source", "junction_source", "intersection_polygon_xy_m",
                    "ego_route_lanes")
        if any(self.context.get(key) is None for key in required):
            raise ValueError("Incomplete original signal context")
        route = self.context["ego_route_lanes"]
        if (not isinstance(route,list) or not route or route[0] !=
                [self.context["ego_road_id"],self.context["ego_lane_id"]] or
                any(not isinstance(pair,list) or len(pair)!=2 or
                    any(type(v) is not int for v in pair) for pair in route)):
            raise ValueError("Sourced ego approach and route lanes required")
        self.paths = [self.root / name for name in
                      ("signal_context.json", "signal_history.jsonl", "video_frames.jsonl",
                       "interaction_history.jsonl", "control_context.json")]
        if any(path.exists() for path in self.paths):
            raise ValueError("Original signal source already exists")
        self.paths[0].write_text(json.dumps(self.context, sort_keys=True, allow_nan=False) + "\n")
        self.paths[4].write_text(json.dumps({
            "intersection_xy_m": self.context["intersection_polygon_xy_m"],
            "native_map_id": self.context["native_map_id"],
            "intersection_id": self.context["intersection_id"]},
            sort_keys=True, allow_nan=False) + "\n")
        self.count = 0
        self.previous = None

    def add_tick(self, world, ego, light, camera_packets, expected_controls_ego,
                 through=None):
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
        if waypoint is None or [waypoint.road_id, waypoint.lane_id] not in self.context["ego_route_lanes"]:
            raise ValueError("Ego left sourced signal route")
        if self.count==0 and [waypoint.road_id,waypoint.lane_id] != [
                self.context["ego_road_id"],self.context["ego_lane_id"]]:
            raise ValueError("Ego did not start on sourced signal approach")
        governed = {(wp.road_id, wp.lane_id) for wp in light.get_affected_lane_waypoints()}
        controls = (self.context["ego_road_id"],self.context["ego_lane_id"]) in governed
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
        interaction = None
        if through is not None:
            if any(self.context.get(key) is None for key in ("through_road_id", "through_lane_id")):
                raise ValueError("Missing sourced through-highway lane")
            through_transform = through.get_transform()
            through_waypoint = native_map.get_waypoint(through_transform.location,
                                                       project_to_road=False)
            through_route = self.context.get("through_route_lanes")
            if (not isinstance(through_route,list) or not through_route or
                    through_route[0] != [self.context["through_road_id"],self.context["through_lane_id"]] or
                    through_waypoint is None or
                    [through_waypoint.road_id, through_waypoint.lane_id] not in through_route):
                raise ValueError("Through actor left sourced highway route")
            def vertices3(actor, actor_transform):
                points = actor.bounding_box.get_world_vertices(actor_transform)
                if len(points) < 4:
                    raise ValueError("Incomplete original actor body")
                return [[_finite(p.x, "body x"), _finite(p.y, "body y"),
                         _finite(p.z, "body z")] for p in points]
            interaction = {"frame": frame, "time_s": time_s,
                           "ego": {"body_vertices_m": vertices3(ego, transform),
                                   "road_id": waypoint.road_id, "lane_id": waypoint.lane_id},
                           "through": {"body_vertices_m": vertices3(through, through_transform),
                                       "road_id": through_waypoint.road_id,
                                       "lane_id": through_waypoint.lane_id}}
        if world.get_snapshot().frame != frame:
            raise ValueError("World advanced during source observation")
        row = {"frame": frame, "time_s": time_s, "native_signal_id": light.id,
               "ego_road_id": waypoint.road_id, "ego_lane_id": waypoint.lane_id,
               "signal_state": state, "signal_controls_ego": controls,
               "ego_speed_mps": speed, "ego_body_vertices_xy_m": body}
        frame_row = {"video_frame": self.count, "carla_frame": frame, "native_frame": frame,
                     "time_s": time_s,
                     "camera_frames": {name: camera_packets[name].frame for name in CAMERAS}}
        for path, value in zip(self.paths[1:], (row, frame_row)):
            with path.open("a") as handle:
                handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        if interaction is not None:
            with self.paths[3].open("a") as handle:
                handle.write(json.dumps(interaction, sort_keys=True, allow_nan=False) + "\n")
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


def run_signal_capture(world, client, root, site, blueprints, transforms, states,
                       target_state, signal_id, expected_controls_ego, context,
                       camera_blueprints, camera_mounts, case_id, required_atoms,
                       drive, frames, sizes=None, capture_factory=None,
                       yield_context=None):
    """Construct a selected signal case and retain its joined original sources.

    ``drive`` applies case-specific actor controls before each Native tick. It
    cannot supply source observations; NativeSignalCapture reads those back.
    """
    if type(frames) is not int or frames < 3 or not callable(drive):
        raise ValueError("A driven three-frame-or-longer Native capture is required")
    if (context.get("native_map_id") != site.get("native_map_id") or
            context.get("ego_route_lanes", [None])[0] != site.get("approach_lanes", {}).get("ego") or
            context.get("through_route_lanes", [None])[0] != site.get("approach_lanes", {}).get("through") or
            context.get("native_signal_id") != signal_id):
        raise ValueError("Capture context differs from selected Native construction")
    is_yield_baseline = case_id.endswith("__yield_without_signal_control")
    if is_yield_baseline != (yield_context is not None):
        raise ValueError("Yield baseline requires its exact authored source context")
    if yield_context is not None:
        if (yield_context.get("native_map_id") != context["native_map_id"] or
                yield_context.get("intersection_id") != context["intersection_id"] or
                yield_context.get("ego_approach_lane") !=
                [context["ego_road_id"], context["ego_lane_id"]] or
                yield_context.get("through_highway_lane") !=
                [context.get("through_road_id"), context.get("through_lane_id")] or
                yield_context.get("sign_type") != "yield" or
                yield_context.get("stop_line_present") is not False or
                yield_context.get("near_crosswalk_present") is not False):
            raise ValueError("Authored yield source differs from selected signed intersection")
    with construct_signal_comparison(world, site, blueprints, transforms, states,
                                     target_state, signal_id, expected_controls_ego) as built:
        with NativeSignalCapture(world, root, built["actors"], built["signal"], context,
                                 expected_controls_ego, camera_blueprints, camera_mounts,
                                 client, case_id, required_atoms, sizes=sizes,
                                 capture_factory=capture_factory) as capture:
            for index in range(frames):
                drive(index, built["actors"])
                capture.capture_tick()
            if capture.encoder.count != frames or capture.writer.count != frames:
                raise ValueError("Native signal source frame count differs from capture plan")
            if yield_context is not None:
                path = Path(root)/"yield_context.json"
                with path.open("x") as source:
                    source.write(json.dumps(yield_context, sort_keys=True, allow_nan=False)+"\n")
    return {"case_id": case_id, "source_frames": frames,
            "source_videos": [name+".mkv" for name in CAMERAS],
            "physical_or_legal_acceptance_claimed": False}
