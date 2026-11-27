"""Lazy CARLA operator for source-reviewed private-way highway approaches.

Every control is an engineering request. Per-frame actor bodies, motion and
camera pixels are read back from CARLA and retained for independent review.
"""
from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
from queue import Empty, Queue
import subprocess
import zipfile

from private_way_site import _inside, _polygon, load_site
from private_way_construction import CASES


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _transform(carla, row):
    _need(isinstance(row, dict) and set(row) == {"x", "y", "z", "yaw"},
          "reviewed Native transform incomplete")
    values = [float(row[key]) for key in ("x", "y", "z", "yaw")]
    _need(all(math.isfinite(value) for value in values),
          "nonfinite reviewed Native transform")
    return carla.Transform(carla.Location(x=values[0], y=values[1], z=values[2]),
                           carla.Rotation(yaw=values[3]))


def _station(point, route):
    best = None
    station = 0.0
    for start, end in zip(route, route[1:]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        span = math.hypot(dx, dy)
        _need(span > .01, "reviewed route contains degenerate segment")
        fraction = max(0.0, min(1.0, ((point[0] - start[0]) * dx +
                                        (point[1] - start[1]) * dy) / (span * span)))
        nearest = (start[0] + fraction * dx, start[1] + fraction * dy)
        candidate = (math.hypot(point[0] - nearest[0], point[1] - nearest[1]),
                     station + fraction * span)
        if best is None or candidate[0] < best[0]:
            best = candidate
        station += span
    _need(best is not None, "reviewed route has no segment")
    return best[1]


class PrivateWayOperator:
    native_attested = True

    def __init__(self, site_packet, case_id, host="127.0.0.1", port=2000):
        import carla
        self.carla = carla
        self.site_packet = Path(site_packet).resolve()
        self.site = load_site(self.site_packet, case_id)
        self.case_id = case_id
        self.variant = case_id.rsplit("__", 1)[-1]
        self.client = carla.Client(host, int(port))
        self.client.set_timeout(20)
        self.world = self.client.get_world()
        self.original_settings = self.world.get_settings()
        self.map_bytes = self.world.get_map().to_opendrive().encode()
        import hashlib
        _need(hashlib.sha256(self.map_bytes).hexdigest() ==
              self.site["sources"]["native_opendrive_map"]["sha256"],
              "loaded CARLA map differs from reviewed Native source")
        for name in ("native_spawn_transforms", "native_vehicle_blueprints",
                     "native_camera_mounts"):
            _need(isinstance(self.site.get(name), dict),
                  "reviewed CARLA site field missing: " + name)
        _need(set(self.site["native_camera_mounts"]) == set(VIEWS),
              "four reviewed camera mounts missing")
        _need(self.site.get("native_camera_mount_frame") == "ego_vehicle_local",
              "camera mount coordinate frame unreviewed")
        self.actors = {}
        self.sensors = []
        self.camera_queues = {}
        self.plan = None
        self.index = 0
        self.last_snapshot = None

    def get_site_packet(self, case_id):
        _need(case_id == self.case_id, "Native site case differs")
        return self.site_packet

    def get_opendrive_bytes(self):
        return self.world.get_map().to_opendrive().encode()

    def _spawn_vehicle(self, identity, route):
        site = self.site
        transform = site["native_spawn_transforms"].get(identity)
        blueprint_id = site["native_vehicle_blueprints"].get(identity)
        _need(isinstance(blueprint_id, str) and blueprint_id.startswith("vehicle.") and
              transform is not None, "reviewed Native vehicle blueprint/spawn missing")
        _need(math.hypot(float(transform["x"]) - route[0][0],
                         float(transform["y"]) - route[0][1]) <= 5.0,
              "reviewed Native spawn differs from route start")
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.try_spawn_actor(blueprint, _transform(self.carla, transform))
        _need(actor is not None, "Native vehicle spawn failed: " + identity)
        self.actors[identity] = actor

    def _spawn_cameras(self):
        ego = self.actors["ego"]
        for view in VIEWS:
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            width, height = SIZES[view]
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("sensor_tick", "0.05")
            sensor = self.world.spawn_actor(
                blueprint,
                _transform(self.carla, self.site["native_camera_mounts"][view]),
                attach_to=ego)
            _need(sensor is not None, "Native camera spawn failed: " + view)
            queue = Queue(maxsize=8)
            sensor.listen(lambda image, target=queue: target.put(image))
            self.sensors.append(sensor)
            self.camera_queues[view] = queue

    def start(self, plan):
        _need(plan["case_id"] == self.case_id and self.plan is None,
              "Native exact case already started or differs")
        self.plan = plan
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        self.world.apply_settings(settings)
        self._spawn_vehicle("ego", plan["ego_route_xy_m"])
        for side, route in plan["highway_approach_routes_xy_m"].items():
            self._spawn_vehicle(side, route)
        self._spawn_cameras()

    def read_actor_inventory(self):
        return {"ego_vehicle_id": self.actors["ego"].id,
                "highway_vehicles": {side: self.actors[side].id
                                     for side in CASES[self.variant][1]},
                "ego_blueprint": self.actors["ego"].type_id,
                "highway_blueprints": {side: self.actors[side].type_id
                                       for side in CASES[self.variant][1]}}

    def _drive(self, actor, route, speed_mps):
        location = actor.get_location()
        point = [location.x, location.y]
        station = _station(point, route)
        target = route[-1]
        for waypoint in route[1:]:
            if _station(waypoint, route) >= station + 4:
                target = waypoint
                break
        heading = math.atan2(target[1] - location.y, target[0] - location.x)
        yaw = math.radians(actor.get_transform().rotation.yaw)
        error = (heading - yaw + math.pi) % (2 * math.pi) - math.pi
        actual = actor.get_velocity().length()
        actor.apply_control(self.carla.VehicleControl(
            throttle=max(0.0, min(.6, .18 * (speed_mps - actual))),
            brake=max(0.0, min(.8, .25 * (actual - speed_mps))),
            steer=max(-.75, min(.75, .8 * error))))

    def _remaining(self, actor, route):
        location = actor.get_location()
        connection = self.site["connection_xy"]
        return _station(connection, route) - _station(
            [location.x, location.y], route)

    def tick(self):
        _need(self.plan is not None, "Native private-way plan not started")
        for side, route in self.plan["highway_approach_routes_xy_m"].items():
            self._drive(self.actors[side], route,
                        self.plan["approach_speed_requests_mps"][side])
        policy = self.plan["requested_control_policy"]
        if policy == "yield_all":
            hold = any(self._remaining(self.actors[side], route) > 0
                       for side, route in self.plan["highway_approach_routes_xy_m"].items())
        elif policy == "yield_one_only":
            hold = self._remaining(self.actors["left"],
                                   self.plan["highway_approach_routes_xy_m"]["left"]) > 0
        else:
            hold = False
        self._drive(self.actors["ego"], self.plan["ego_route_xy_m"],
                    0.0 if hold else 3.0)
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        _need(snapshot.frame == frame, "CARLA tick and snapshot differ")
        self.last_snapshot = snapshot
        self.index += 1
        return {"frame": frame, "time_s": snapshot.timestamp.elapsed_seconds}

    def _body(self, actor):
        return [[vertex.x, vertex.y, vertex.z] for vertex in
                actor.bounding_box.get_world_vertices(actor.get_transform())]

    def read_motion(self, frame):
        _need(self.last_snapshot is not None and self.last_snapshot.frame == frame,
              "Native motion requested for wrong tick")
        ego = self.actors["ego"]
        body = self._body(ego)
        highway = _polygon(self.site["highway_polygon"], "highway")
        managed_ids = {actor.id for actor in self.actors.values()}
        for actor in self.world.get_actors().filter("vehicle.*"):
            if actor.id in managed_ids or not actor.is_alive:
                continue
            point = actor.get_location()
            if _inside((point.x, point.y), highway):
                raise ValueError("unmanaged highway vehicle could violate all-approaches inventory")
        others = []
        for side in CASES[self.variant][1]:
            actor = self.actors[side]
            point = actor.get_location()
            others.append({"actor_id": actor.id, "side": side,
                           "xy_m": [point.x, point.y],
                           "body_vertices_m": self._body(actor),
                           "distance_to_connection_m": self._remaining(
                               actor, self.plan["highway_approach_routes_xy_m"][side]),
                           "speed_mps": actor.get_velocity().length()})
        return {"native_frame": frame, "case_id": self.case_id,
                "source_kind": "original_native", "ego_vehicle_id": ego.id,
                "ego_xy_m": [ego.get_location().x, ego.get_location().y],
                "ego_body_vertices_m": body,
                "ego_on_highway": any(_inside((vertex[0], vertex[1]), highway)
                                      for vertex in body),
                "ego_speed_mps": ego.get_velocity().length(),
                "ego_brake": ego.get_control().brake,
                "highway_vehicles": others}

    def read_cameras(self, frame):
        from PIL import Image
        output = {}
        for view in VIEWS:
            queue = self.camera_queues[view]
            try:
                image = queue.get(timeout=10)
                while image.frame < frame:
                    image = queue.get(timeout=10)
            except Empty as error:
                raise ValueError("original CARLA camera timed out: " + view) from error
            _need(image.frame == frame, "original CARLA camera frame gap: " + view)
            bitmap = Image.frombytes("RGBA", (image.width, image.height),
                                     image.raw_data, "raw", "BGRA")
            buffer = BytesIO()
            bitmap.convert("RGB").save(buffer, format="PNG")
            output[view] = {"frame": frame,
                            "time_s": self.last_snapshot.timestamp.elapsed_seconds,
                            "png": buffer.getvalue()}
        return output

    def brake(self):
        if "ego" in self.actors:
            self.actors["ego"].apply_control(self.carla.VehicleControl(brake=1.0))

    def cleanup(self):
        try:
            for sensor in reversed(self.sensors):
                sensor.stop()
                sensor.destroy()
            for actor in reversed(list(self.actors.values())):
                actor.destroy()
        finally:
            self.world.apply_settings(self.original_settings)

    def encode_media(self, root, cameras, frame_map):
        root = Path(root)
        media = {}
        for view in cameras:
            frames = root / ("encode-" + view)
            frames.mkdir()
            with zipfile.ZipFile(root / (view + ".zip")) as archive:
                for index, entry in enumerate(frame_map):
                    member = f"{index:04d}-{entry['native_frame']}.png"
                    (frames / f"{index:04d}.png").write_bytes(archive.read(member))
            output = root / (view + ".mkv")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "20",
                            "-i", str(frames / "%04d.png"), "-c:v", "ffv1",
                            str(output)], check=True, timeout=300)
            media[view] = str(output)
            import shutil
            shutil.rmtree(frames)
        raw = root / "raw.mkv"
        command = ["ffmpeg", "-v", "error", "-y"]
        for view in cameras:
            command.extend(["-i", media[view]])
        command.extend(["-filter_complex",
                        "[0:v]scale=640:360[a];[1:v]scale=640:360[b];"
                        "[2:v]scale=640:360[c];[3:v]scale=640:360[d];"
                        "[a][b][c][d]xstack=inputs=4:layout=0_0|640_0|0_360|640_360[out]",
                        "-map", "[out]", "-c:v", "ffv1", str(raw)])
        subprocess.run(command, check=True, timeout=300)
        media["raw"] = str(raw)
        return media


def create(site_packet, case_id, host="127.0.0.1", port=2000):
    return PrivateWayOperator(site_packet, case_id, host, port)
