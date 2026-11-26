"""Lazy CARLA Native adapter for source-gated hose capture.

Reviewed packet poses and blueprints are mandatory. The resulting physical
motion and pixels still require independent original-source audit.
"""

import io
import math
from queue import Empty, Queue


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def steering_to(current_xy, yaw_degrees, target_xy):
    desired = math.atan2(target_xy[1] - current_xy[1], target_xy[0] - current_xy[0])
    error = (desired - math.radians(yaw_degrees) + math.pi) % (2 * math.pi) - math.pi
    return max(-1.0, min(1.0, error / 0.7))


def body_corners(transform, extent):
    yaw = math.radians(transform.rotation.yaw)
    c, s = math.cos(yaw), math.sin(yaw)
    x, y = transform.location.x, transform.location.y
    return [[x + dx * c - dy * s, y + dx * s + dy * c]
            for dx, dy in ((-extent.x, -extent.y), (extent.x, -extent.y),
                           (extent.x, extent.y), (-extent.x, extent.y))]


class Adapter:
    def __init__(self, config, host, port):
        import carla
        self.carla = carla
        self.config = config
        self.client = carla.Client(host, port)
        self.client.set_timeout(20.0)
        self.world = self.client.get_world()
        self.ego = None
        self.route = None
        self.camera_poses = None
        self.sensors = {}
        self.queues = {}
        self.pending = {}

    def provenance(self):
        return "original_native"

    def pose(self, values):
        if not isinstance(values, list) or len(values) != 4:
            raise ValueError("reviewed original [x,y,z,yaw] pose required")
        x, y, z, yaw = values
        if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
            raise ValueError("reviewed original pose must be finite")
        return self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                    self.carla.Rotation(yaw=yaw))

    def snapshot_settings(self):
        return self.world.get_settings()

    def set_synchronous(self, delta):
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = delta
        self.world.apply_settings(settings)

    def hose_transform(self, reviewed):
        return self.pose(reviewed["hose"]["pose_xyzyaw"])

    def spawn_ego(self, vehicle, private_way):
        blueprint_id = vehicle.get("blueprint_id")
        if not blueprint_id or not blueprint_id.startswith("vehicle."):
            raise ValueError("reviewed vehicle blueprint missing")
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        if blueprint is None or blueprint.id != blueprint_id:
            raise ValueError("reviewed vehicle blueprint unavailable")
        actor = self.world.try_spawn_actor(blueprint, self.pose(vehicle["pose_xyzyaw"]))
        if actor is None or self.world.get_actor(actor.id) is None:
            raise ValueError("original ego spawn/readback failed")
        self.ego = actor
        self.camera_poses = private_way.get("camera_poses_xyzyaw")
        return actor

    def set_route(self, ego, points, crossing):
        if ego is not self.ego or not isinstance(points, list) or len(points) < 2:
            raise ValueError("reviewed original ego route missing")
        if any(not isinstance(p, list) or len(p) != 2 for p in points):
            raise ValueError("reviewed original route coordinates missing")
        self.route = [tuple(p) for p in points]
        self.waypoint = 1
        self.planned_crossing = crossing

    def start_cameras(self, views):
        if tuple(views) != VIEWS or not isinstance(self.camera_poses, dict) or set(self.camera_poses) != set(VIEWS):
            raise ValueError("reviewed original four camera poses required")
        for view in VIEWS:
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            width, height = self.config["camera_dimensions"][view]
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("sensor_tick", "0.05")
            sensor = self.world.try_spawn_actor(blueprint, self.pose(self.camera_poses[view]))
            if sensor is None or self.world.get_actor(sensor.id) is None:
                raise ValueError("original camera spawn/readback failed")
            queue = Queue()
            sensor.listen(queue.put)
            self.sensors[view] = sensor
            self.queues[view] = queue
            self.pending[view] = {}

    def tick(self):
        transform = self.ego.get_transform()
        xy = (transform.location.x, transform.location.y)
        target = self.route[self.waypoint]
        if math.dist(xy, target) < 1.5 and self.waypoint < len(self.route) - 1:
            self.waypoint += 1
            target = self.route[self.waypoint]
        finished = self.waypoint == len(self.route) - 1 and math.dist(xy, target) < 1.0
        steer = steering_to(xy, transform.rotation.yaw, target)
        self.ego.apply_control(self.carla.VehicleControl(throttle=0.0 if finished else 0.28,
                                                          steer=steer, brake=1.0 if finished else 0.0))
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("original world snapshot frame differs")
        return {"frame": frame, "time_s": snapshot.timestamp.elapsed_seconds}

    def observe(self, snapshot, hose):
        actor = self.world.get_actor(self.ego.id)
        actual_hose = self.world.get_actor(hose.id)
        if actor is None or actual_hose is None or not actual_hose.is_alive:
            raise ValueError("original ego or hose actor disappeared")
        transform = actor.get_transform()
        return {"ego_xy": [transform.location.x, transform.location.y],
                "ego_body_corners_xy": body_corners(transform, actor.bounding_box.extent),
                "ego_actor_id": actor.id}

    def camera_packets(self, snapshot):
        from PIL import Image
        frame = snapshot["frame"]
        packets = {}
        for view in VIEWS:
            image = self.pending[view].pop(frame, None)
            while image is None:
                try:
                    candidate = self.queues[view].get(timeout=10.0)
                except Empty as exc:
                    raise ValueError("original camera source timed out") from exc
                if candidate.frame == frame:
                    image = candidate
                elif candidate.frame > frame:
                    self.pending[view][candidate.frame] = candidate
                else:
                    raise ValueError("stale original camera frame")
            rgba = Image.frombytes("RGBA", (image.width, image.height),
                                   bytes(image.raw_data), "raw", "BGRA")
            stream = io.BytesIO()
            rgba.convert("RGB").save(stream, format="PNG")
            packets[view] = {"frame": image.frame, "time_s": image.timestamp,
                             "sensor_id": self.sensors[view].id, "width": image.width,
                             "height": image.height, "png": stream.getvalue()}
        return packets

    def stop_cameras(self):
        for sensor in self.sensors.values():
            try:
                sensor.stop()
            finally:
                sensor.destroy()
        self.sensors.clear()

    def destroy(self, actor):
        actor.destroy()

    def restore_settings(self, settings):
        self.world.apply_settings(settings)


def create_adapter(config, host, port):
    return Adapter(config, host, port)
