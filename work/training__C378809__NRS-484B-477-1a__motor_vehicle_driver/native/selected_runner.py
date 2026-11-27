"""Prospective source-gated three-case alley/goods Native acquisition.

No frame, goods script, or case name establishes a legal finding. Original site
review and independent saved video review remain required.
"""
import argparse
import json
import math
import os
from pathlib import Path
import queue
import subprocess

from selected_plan import CASES, plan, review_survey


HERE = Path(__file__).resolve().parent
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    require(config.get("supported_case_ids") == list(CASES),
            "selected case inventory changed")
    require(config.get("law_id") == "NRS-484B-477-1a" and
            config.get("cell_id") == "C378809" and
            config.get("actor") == "motor_vehicle_driver", "exact assignment changed")
    require(config.get("rate_hz") == 20 and config.get("duration_s") == 30 and
            config.get("frames") == 600, "30-second capture missing")
    cameras = config.get("cameras", [])
    require(tuple(c.get("name") for c in cameras) == VIEWS,
            "four-camera profile names/order missing")
    require([(c["width"], c["height"]) for c in cameras] ==
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] and
            all(c.get("fps") == 20 and c.get("pose_strategy") and c.get("fov_deg")
                for c in cameras), "four-camera profile geometry missing")
    return {"case_ids": list(CASES), "frames": 600, "views": list(VIEWS),
            "simulation_started": False, "physical_completion": False}


def load_survey(path):
    require(path, "original alley survey required")
    return review_survey(json.loads(Path(path).read_text()))


def execute(config, case_id, survey_path, output_dir, host, port):
    check(config)
    require(case_id in CASES, "unknown exact case")
    survey = load_survey(survey_path)
    request = plan(case_id, survey)
    require(".runtime-work" in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""),
            "output root must be under .runtime-work")
    output = Path(output_dir)
    require(not output.exists(), "new original attempt required")
    output.mkdir(parents=True)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    prior = snapshot(client)
    owned = []
    sensors = []
    encoders = {}
    pixels = queue.Queue()
    complete = False
    try:
        require(world.get_map().name == survey["map_name"],
                "surveyed map differs from original world")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        bp = world.get_blueprint_library()
        vehicle_bp = bp.find(survey["vehicle_blueprint"])
        require(vehicle_bp is not None, "surveyed vehicle unavailable")
        x, y, z, yaw = survey["spawn_xyz_yaw_deg"]
        vehicle = world.try_spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))
        require(vehicle is not None, "surveyed spawn occupied")
        owned.append(vehicle)
        goods = None
        if request["goods_motion_requested"]:
            goods_bp = bp.find(survey["goods_blueprint"])
            require(goods_bp is not None, "surveyed goods prop unavailable")
            gx, gy, gz = survey["goods_origin_xyz_m"]
            goods = world.try_spawn_actor(goods_bp, carla.Transform(
                carla.Location(x=gx, y=gy, z=gz)))
            require(goods is not None, "surveyed goods source occupied")
            owned.append(goods)
        for camera in config["cameras"]:
            sensor_bp = bp.find("sensor.camera.rgb")
            sensor_bp.set_attribute("image_size_x", str(camera["width"]))
            sensor_bp.set_attribute("image_size_y", str(camera["height"]))
            sensor_bp.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, cyaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(sensor_bp, carla.Transform(
                carla.Location(x=cx, y=cy, z=cz),
                carla.Rotation(pitch=pitch, yaw=cyaw, roll=roll)), attach_to=vehicle)
            owned.append(sensor)
            sensors.append(sensor)
            encoders[camera["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s",
                f'{camera["width"]}x{camera["height"]}', "-r", "20", "-i", "-",
                "-frames:v", "600", "-c:v", "ffv1", "-level", "1",
                str(output / (camera["name"] + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            sensor.listen(lambda image, name=camera["name"]: pixels.put((name, image)))
        with PipelineCapture(client, vehicle, output, case_id,
                             required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "alley-native.jsonl").open("x", buffering=1) as trace:
            for index in range(600):
                pose = vehicle.get_transform()
                velocity = vehicle.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                target = survey["park_xyz_m"]
                dx = target[0] - pose.location.x
                dy = target[1] - pose.location.y
                distance = math.hypot(dx, dy)
                heading = math.atan2(dy, dx)
                relative = math.atan2(math.sin(heading - math.radians(pose.rotation.yaw)),
                                      math.cos(heading - math.radians(pose.rotation.yaw)))
                vehicle.apply_control(carla.VehicleControl(
                    throttle=.25 if distance > 2 and speed < 3 else 0,
                    brake=1 if distance <= 2 else 0,
                    steer=max(-.35, min(.35, relative))))
                # The prop motion is a requested visible cue, never proof that a
                # person transferred goods or that the statutory exception applies.
                goods_motion_frame = request["goods_motion_frame"]
                if goods is not None and index == goods_motion_frame:
                    gx, gy, gz = survey["goods_destination_xyz_m"]
                    goods.set_transform(carla.Transform(carla.Location(x=gx, y=gy, z=gz)))
                native_frame = world.tick()
                observed = vehicle.get_transform()
                observed_velocity = vehicle.get_velocity()
                seen = set()
                while len(seen) < 4:
                    name, image = pixels.get(timeout=30)
                    if image.frame != native_frame or name in seen:
                        continue
                    encoders[name].stdin.write(image.raw_data)
                    seen.add(name)
                capture.capture(native_frame, index / 20, extra={"video_frame": index})
                frame_map.append(native_frame, index / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({
                    "source_kind": "original_native_observation", "case_id": case_id,
                    "frame": index, "native_frame": native_frame, "t_s": index / 20,
                    "vehicle_id": vehicle.id,
                    "alley_boundary_source_id": survey["alley_boundary_source_id"],
                    "position_xyz_m": [observed.location.x, observed.location.y,
                                       observed.location.z],
                    "velocity_xyz_mps": [observed_velocity.x, observed_velocity.y,
                                         observed_velocity.z],
                    "goods_prop_id": goods.id if goods else None,
                    "goods_prop_motion_requested": bool(goods and index == goods_motion_frame),
                    "original_goods_transfer_verified": False,
                    "ordinance_status_source_id": survey["ordinance_status_source_id"]
                }) + "\n")
        for encoder in encoders.values():
            encoder.stdin.close()
            require(encoder.wait(timeout=180) == 0,
                    "original camera encoder failed")
        # Keep every source view and compose the primary without scaling.
        composition = subprocess.run([
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(output / "overview.mkv"),
            "-i", str(output / "approach.mkv"),
            "-i", str(output / "reference_corner.mkv"),
            "-i", str(output / "driver_reference.mkv"),
            "-filter_complex",
            "[0:v]pad=3840:1080:960:0[top];"
            "[1:v][2:v][3:v]hstack=inputs=3[bottom];"
            "[top][bottom]vstack=inputs=2[all]",
            "-map", "[all]", "-frames:v", "600", "-c:v", "ffv1",
            str(output / "primary.mkv")], capture_output=True, timeout=300)
        require(composition.returncode == 0, "four-view primary composition failed")
        complete = True
    finally:
        for encoder in encoders.values():
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(owned):
            actor.destroy()
        restore(client, prior)
    return {"case_id": case_id, "complete_attempt": complete,
            "original_goods_transfer_verified": False, "legal_result": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--alley-survey")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((HERE / "config.json").read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        require(args.case and args.output_dir, "exact case and output required")
        print(json.dumps(execute(config, args.case, args.alley_survey or
              os.environ.get("SCENARIO_ALLEY_SURVEY"), args.output_dir,
              args.host, args.port), sort_keys=True))
