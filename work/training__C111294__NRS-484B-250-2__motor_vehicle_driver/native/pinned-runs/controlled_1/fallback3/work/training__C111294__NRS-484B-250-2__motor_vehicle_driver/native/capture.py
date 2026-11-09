"""Unaccepted original CARLA two-highway entry attempt for C111294."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from build import FRAMES, RATE
from check import check


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def xyz(value):
    return [value.x, value.y, value.z]


def actor_row(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    return {"actor_id": actor.id, "blueprint": actor.type_id,
            "center_native_xyz_m": xyz(transform.location),
            "yaw_deg": transform.rotation.yaw,
            "velocity_native_xyz_mps": xyz(velocity),
            "speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
            "body_native_xyz_m": [xyz(point) for point in actor.bounding_box.get_world_vertices(transform)]}


def control(actor, request, carla):
    target = request["requested_ego_speed_mps"]
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    if target == 0:
        return carla.VehicleControl(throttle=0, brake=min(1, .4 + speed/5), steer=0)
    return carla.VehicleControl(throttle=max(.1, min(.7, .3 + .12*(target-speed))),
                                brake=0, steer=0)


def capture(bundle, output, host, port):
    import carla
    import numpy as np
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    client = carla.Client(host, int(port)); client.set_timeout(180)
    previous = client.get_world()
    saved_world = snapshot(client)
    if previous.get_settings().synchronous_mode or any(a.type_id.startswith(("vehicle.", "walker.", "sensor."))
                                                for a in previous.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous CARLA world required")
    output.mkdir(parents=True, exist_ok=False)
    owned, sensors, encoders, logs = [], {}, {}, {}
    changed = False; frames = 0; error = None; restoration = None
    try:
        world = client.generate_opendrive_world((bundle / "crossroads.xodr").read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings(); settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        lane_readback = {}
        for name, road_id, station in (("ego_approach",250,30),("ego_connector",251,20),
                                       ("ego_departure",252,10),("other_approach",253,30),
                                       ("other_connector",254,20),("other_departure",255,10)):
            wp = mapping.get_waypoint_xodr(road_id, -1, station)
            if wp is None or wp.road_id != road_id or wp.lane_id != -1 or wp.lane_type != carla.LaneType.Driving:
                raise RuntimeError("Generated driving lane missing: " + name)
            lane_readback[name] = {"road_id": wp.road_id, "lane_id": wp.lane_id,
                                   "native_xyz_m": xyz(wp.transform.location),
                                   "lane_type": str(wp.lane_type)}
        ego_junction = mapping.get_waypoint_xodr(251, -1, 20).get_junction()
        other_junction = mapping.get_waypoint_xodr(254, -1, 20).get_junction()
        if ego_junction is None or other_junction is None or ego_junction.id != 1 or other_junction.id != 1:
            raise RuntimeError("Generated two-highway junction missing")
        library = world.get_blueprint_library()
        ego = world.try_spawn_actor(library.find(cfg["ego_blueprint"]),
            carla.Transform(carla.Location(x=-50,y=-1.75,z=1.5), carla.Rotation(yaw=0)))
        other = world.try_spawn_actor(library.find(cfg["other_blueprint"]),
            carla.Transform(carla.Location(x=1.75,y=-50,z=1.5), carla.Rotation(yaw=90)))
        if ego is None or other is None:
            raise RuntimeError("Both physical vehicles must spawn")
        owned.extend((ego,other))
        overview_height = 50 if cfg["camera_policy"] == "elevated_overview" else 35
        specs = (("ego_view",1280,720,(-45,-8,3),0,-5),
                 ("other_view",1280,720,(8,-45,3),90,-5),
                 ("overview",1280,720,(0,0,overview_height),-45,-90))
        for name,width,height,location,yaw,pitch in specs:
            bp = library.find("sensor.camera.rgb")
            for key,value in (("image_size_x",width),("image_size_y",height),("fov",80),("sensor_tick",0)):
                bp.set_attribute(key,str(value))
            sensor = world.spawn_actor(bp,carla.Transform(carla.Location(*location),
                                                          carla.Rotation(yaw=yaw,pitch=pitch)))
            owned.append(sensor); sensors[name]=queue.Queue(); sensor.listen(sensors[name].put)
            logs[name]=(output/(name+".encoder.log")).open("x")
            encoders[name]=subprocess.Popen(["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
                "-n","-f","rawvideo","-pix_fmt","rgb24","-s",f"{width}x{height}",
                "-r",str(RATE),"-i","pipe:0","-an","-c:v","ffv1",str(output/(name+".mkv"))],
                stdin=subprocess.PIPE,stderr=logs[name])
        (output/"native-map-readback.json").write_text(json.dumps({
            "source_kind":"original_native","road_sha256":sha(bundle/"crossroads.xodr"),
            "native_map_sha256":hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            "lane_readback":lane_readback,"junction_id":1,"authored_signal_count":0,
            "ego_actor_id":ego.id,"other_actor_id":other.id,"legal_verdict":None},indent=2)+"\n")
        for _ in range(20): world.tick()
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output/"native-raw-actors.jsonl").open("x") as actor_file, \
             (output/"video_frames.jsonl").open("x") as video_file:
            for i,request in enumerate(requests):
                ego.apply_control(control(ego,requests[min(i+5,FRAMES-1)],carla))
                other.set_target_velocity(carla.Vector3D(x=0,y=request["requested_other_speed_mps"],z=0))
                native_frame=world.tick()
                t=world.get_snapshot().timestamp.elapsed_seconds-start
                ego_state,other_state=actor_row(ego),actor_row(other)
                ego_wp=mapping.get_waypoint(ego.get_location(),project_to_road=False,lane_type=carla.LaneType.Any)
                other_wp=mapping.get_waypoint(other.get_location(),project_to_road=False,lane_type=carla.LaneType.Any)
                actor_file.write(json.dumps({"frame":i,"native_frame":native_frame,"time_s":t,
                    "source_kind":"original_native","request_frame":request["frame"],
                    "ego":ego_state,"other":other_state,
                    "ego_road_id":None if ego_wp is None else ego_wp.road_id,
                    "other_road_id":None if other_wp is None else other_wp.road_id,
                    "requested_ego_phase":request["requested_ego_phase"],
                    "authored_official_device_count":0,"legal_verdict":None},allow_nan=False)+"\n")
                for name,width,height,*_ in specs:
                    image=sensors[name].get(timeout=30)
                    while image.frame<native_frame: image=sensors[name].get(timeout=30)
                    if image.frame!=native_frame: raise RuntimeError("Camera/native frame join failed")
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(height,width,4)[:,:,:3][:,:,::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                video_file.write(json.dumps({"video_frame":i,"native_frame":native_frame,"time_s":t})+"\n")
                frames+=1
    except BaseException as exc:
        error={"type":type(exc).__name__,"message":str(exc),"traceback":traceback.format_exc()}
    finally:
        for name,encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180)!=0: raise RuntimeError("FFV1 encoder failed")
            except BaseException as exc: error=error or {"encoder_error":str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening: actor.stop()
                actor.destroy()
            except BaseException as exc: error=error or {"cleanup_error":str(exc)}
        if changed:
            try: restoration=restore(client,saved_world)
            except BaseException as exc: error=error or {"restore_error":str(exc)}
        (output/"native-capture-report.json").write_text(json.dumps({
            "case_id":cfg["case_id"],"candidate_id":cfg["candidate_id"],
            "config_sha256":sha(bundle/"config.json"),"requested_frames":FRAMES,
            "observed_frames":frames,"restoration":restoration,"error":error,
            "accepted":False,"delivery_ready":False,"legal_verdict":None},indent=2)+"\n")
    if error: raise RuntimeError("C111294 original Native attempt failed; inspect capture report")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--bundle",type=Path,default=Path.cwd())
    parser.add_argument("--output-dir",type=Path)
    parser.add_argument("--host",default="localhost")
    parser.add_argument("--port",type=int,default=2000)
    args=parser.parse_args()
    if args.check: print(json.dumps(check(args.bundle)))
    else:
        if args.output_dir is None: parser.error("Original output directory required")
        capture(args.bundle,args.output_dir,args.host,args.port)
