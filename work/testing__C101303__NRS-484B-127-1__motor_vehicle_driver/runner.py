"""C101303 Native capture. Importing and --check never contact CARLA."""
import argparse
import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def check(config):
    assert config["cell_id"] == "C101303"
    assert config["law_id"] == "NRS-484B-127-1"
    assert config["actor"] == "motor_vehicle_driver"
    assert config["selected_case_id"] in config["supported_case_ids"]
    assert config["rate_hz"] == 20 and config["duration_s"] == 45
    assert len(config["cameras"]) == 4
    assert config["initial_gap_m"] in (16.0, 26.0)
    assert config["controller"]["target_speed_mps"] > 0
    return config


def _adjacent(wp, carla):
    left = wp.get_left_lane()
    return (left is not None and left.lane_type == carla.LaneType.Driving
            and left.road_id == wp.road_id and left.lane_id * wp.lane_id > 0)


def find_crest(world, carla):
    """Require a measured local elevation maximum and connected passing lane."""
    candidates = []
    for wp in world.get_map().generate_waypoints(3.0):
        if not _adjacent(wp, carla) or wp.is_junction:
            continue
        before, after = wp.previous(60), wp.next(80)
        if len(before) != 1 or len(after) != 1:
            continue
        approach = before[0]
        if approach.road_id != wp.road_id or not _adjacent(approach, carla):
            continue
        near_before, near_after = wp.previous(12), wp.next(12)
        if len(near_before) != 1 or len(near_after) != 1:
            continue
        rise = wp.transform.location.z - near_before[0].transform.location.z
        fall = wp.transform.location.z - near_after[0].transform.location.z
        if rise >= 0.15 and fall >= 0.15:
            candidates.append((min(rise, fall), wp))
    if not candidates:
        raise RuntimeError("No measured hill crest with connected same-direction lane")
    crest = max(candidates, key=lambda row: row[0])[1]
    return crest


def _back(wp, distance):
    prior = wp.previous(distance)
    if len(prior) != 1:
        raise RuntimeError("Route predecessor is ambiguous")
    return prior[0]


def _spawn(world, carla, bp, wp):
    transform = wp.transform
    transform.location.z += 0.6
    vehicle = world.try_spawn_actor(bp, transform)
    if vehicle is None:
        raise RuntimeError("Native vehicle spawn failed")
    return vehicle


def _speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def _vertices(actor):
    return [[v.x, v.y, v.z] for v in actor.bounding_box.get_world_vertices(actor.get_transform())]


def _drive(actor, waypoint, speed, dt, state, carla, lookahead):
    nxt = waypoint.next(lookahead)
    target = nxt[0].transform.location if len(nxt) == 1 else waypoint.transform.location
    transform = actor.get_transform()
    delta = target - transform.location
    desired = math.degrees(math.atan2(delta.y, delta.x))
    error = (desired - transform.rotation.yaw + 180) % 360 - 180
    steer = max(-0.65, min(0.65, error * 0.025))
    actual = _speed(actor)
    state["integral"] = max(-4.0, min(4.0, state["integral"] + (speed - actual) * dt))
    effort = 0.42 * (speed - actual) + 0.05 * state["integral"]
    actor.apply_control(carla.VehicleControl(throttle=max(0, min(0.75, effort)),
                                         brake=max(0, min(0.8, -effort)), steer=steer))


class Encoder:
    def __init__(self, path, width, height, fps):
        self.path = Path(path)
        self.proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                      "-f", "rawvideo", "-pixel_format", "bgra",
                                      "-video_size", f"{width}x{height}", "-framerate", str(fps),
                                      "-i", "pipe:0", "-an", "-c:v", "ffv1", str(path)],
                                     stdin=subprocess.PIPE)

    def append(self, image):
        self.proc.stdin.write(image.raw_data)

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait(timeout=90):
            raise RuntimeError(f"ffmpeg failed for {self.path}")


def _image(q, frame):
    while True:
        image = q.get(timeout=30)
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise RuntimeError("Camera skipped Native frame")


def capture(config, output, host, port):
    import carla  # Native only
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import fields

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original_settings = world.get_settings()
    original_weather = world.get_weather()
    owned = []
    sensors = {}
    encoders = {}
    restoration = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        if world.get_settings().fixed_delta_seconds != 0.05:
            raise RuntimeError("Synchronous 20 Hz readback failed")
        crest = find_crest(world, carla)
        lead_wp = _back(crest, 10)
        ego_wp = _back(lead_wp, config["initial_gap_m"])
        if ego_wp.road_id != lead_wp.road_id or ego_wp.lane_id != lead_wp.lane_id:
            raise RuntimeError("Following spawn does not share lead lane")
        bp = world.get_blueprint_library().filter("vehicle.tesla.model3")
        if not bp:
            bp = world.get_blueprint_library().filter("vehicle.*")
        if not bp:
            raise RuntimeError("No vehicle blueprint")
        lead = _spawn(world, carla, bp[0], lead_wp)
        owned.append(lead)
        ego = _spawn(world, carla, bp[0], ego_wp)
        owned.append(ego)
        center = crest.transform.location
        poses = {
            "overview": carla.Transform(carla.Location(x=center.x, y=center.y, z=center.z + 70), carla.Rotation(pitch=-90)),
            "approach": carla.Transform(carla.Location(x=ego_wp.transform.location.x, y=ego_wp.transform.location.y, z=ego_wp.transform.location.z + 18), carla.Rotation(pitch=-65, yaw=ego_wp.transform.rotation.yaw)),
            "reference_corner": carla.Transform(carla.Location(x=center.x + 18, y=center.y + 18, z=center.z + 18), carla.Rotation(pitch=-35, yaw=crest.transform.rotation.yaw + 180)),
            "driver_reference": carla.Transform(carla.Location(x=-7, z=3), carla.Rotation(pitch=-10)),
        }
        for camera in config["cameras"]:
            name = camera["name"]
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(camera["width"]))
            blueprint.set_attribute("image_size_y", str(camera["height"]))
            blueprint.set_attribute("fov", str(camera["fov_deg"]))
            attach = ego if name == "driver_reference" else None
            sensor = world.spawn_actor(blueprint, poses[name], attach_to=attach)
            owned.append(sensor)
            q = queue.Queue(maxsize=3)
            sensor.listen(q.put)
            sensors[name] = q
            encoders[name] = Encoder(output / f"{name}.mkv", camera["width"], camera["height"], 20)
        context = {"format": "c101303-native-surface-context", "map": world.get_map().name,
                   "road_id": crest.road_id, "crest_location_m": [center.x, center.y, center.z],
                   "crest_elevation_m": center.z, "initial_lane_id": ego_wp.lane_id,
                   "target_lane_id": crest.get_left_lane().lane_id,
                   "highway_public_status": "not established by Native map; local source review required",
                   "weather_at_start": fields(world.get_weather())}
        write(output / "surface_context.json", context)
        pipeline = PipelineCapture(client, ego, output, config["selected_case_id"],
                                   required_observations=config["required_atoms"])
        stream = (output / "following_samples.jsonl").open("x")
        ego_state, lead_state = {"integral": 0.0}, {"integral": 0.0}
        target_lane = context["target_lane_id"]
        try:
            with FrameMap(output / "video_frames.jsonl") as frame_map:
                for i in range(900):
                    ego_waypoint = world.get_map().get_waypoint(ego.get_location(), project_to_road=True,
                                                                lane_type=carla.LaneType.Driving)
                    lead_waypoint = world.get_map().get_waypoint(lead.get_location(), project_to_road=True,
                                                                 lane_type=carla.LaneType.Driving)
                    if ego_waypoint is None or lead_waypoint is None:
                        raise RuntimeError("Native lane lookup lost")
                    lane_change_requested = i >= 440
                    target = ego_waypoint
                    if lane_change_requested and ego_waypoint.lane_id != target_lane:
                        target = ego_waypoint.get_left_lane()
                        if target is None or target.lane_type != carla.LaneType.Driving:
                            raise RuntimeError("Target lane unavailable during lane change")
                    _drive(ego, target, config["controller"]["target_speed_mps"], .05,
                           ego_state, carla, config["controller"]["lookahead_m"])
                    _drive(lead, lead_waypoint, config["controller"]["lead_speed_mps"], .05,
                           lead_state, carla, config["controller"]["lookahead_m"])
                    frame = world.tick()
                    t = i * .05
                    frame_map.append(frame, t)
                    for name, q in sensors.items():
                        encoders[name].append(_image(q, frame))
                    ego_waypoint = world.get_map().get_waypoint(ego.get_location(), project_to_road=True,
                                                                lane_type=carla.LaneType.Driving)
                    lead_waypoint = world.get_map().get_waypoint(lead.get_location(), project_to_road=True,
                                                                 lane_type=carla.LaneType.Driving)
                    if ego_waypoint is None or lead_waypoint is None:
                        raise RuntimeError("Native lane lookup lost after tick")
                    ev = ego.get_velocity(); lv = lead.get_velocity()
                    row = {"frame": frame, "time_s": t, "ego_body_vertices_m": _vertices(ego),
                           "lead_body_vertices_m": _vertices(lead), "ego_lane_id": ego_waypoint.lane_id,
                           "lead_lane_id": lead_waypoint.lane_id, "ego_speed_mps": _speed(ego),
                           "lead_speed_mps": _speed(lead), "ego_velocity_mps": [ev.x, ev.y, ev.z],
                           "lead_velocity_mps": [lv.x, lv.y, lv.z], "lane_change_requested": lane_change_requested,
                           "weather": fields(world.get_weather())}
                    stream.write(json.dumps(row, allow_nan=False) + "\n")
                    pipeline.capture(frame, t, extra={"lead_actor_id": lead.id,
                                                       "lead_speed_mps": row["lead_speed_mps"]})
        finally:
            stream.close()
            pipeline.close(confirmed=False if frame_map.index != 900 else True)
            for sensor in owned[2:]:
                sensor.stop()
            for encoder in encoders.values():
                encoder.close()
        write(output / "acquisition-provenance.json", {"provenance_kind": "native",
            "diagnostic_fixture": False, "map": world.get_map().name,
            "frames": 900, "case_id": config["selected_case_id"]})
    finally:
        try:
            for actor in reversed(owned):
                actor.destroy()
        finally:
            world.apply_settings(original_settings)
            world.set_weather(original_weather)
            actual = world.get_settings()
            if (actual.synchronous_mode != original_settings.synchronous_mode or
                    actual.fixed_delta_seconds != original_settings.fixed_delta_seconds):
                raise RuntimeError("World settings restoration readback failed")
            restoration = {"restored": True, "settings": fields(actual),
                           "weather": fields(world.get_weather()),
                           "map": world.get_map().name}
    seal_capture(output, frames=900, restoration=restoration, errors=[],
                 encoder_exit_codes={name: 0 for name in encoders})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--output-dir")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2000)
    args = p.parse_args()
    config = check(load(Path(__file__).with_name("config.json")))
    if args.check:
        print("C101303 configuration checked; no CARLA connection")
        return
    if not args.output_dir:
        p.error("--output-dir is required for Native capture")
    capture(config, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
