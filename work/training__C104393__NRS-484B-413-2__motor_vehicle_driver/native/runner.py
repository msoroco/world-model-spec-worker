"""Owned CARLA hill-crest capture. Physical success requires saved review."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from cameras import camera_plan
from controller import PathController
from engineering import parameters
from geometry import check as geometry_check, open_drive
from signal_control import left_signal_requested

ROOT = Path(__file__).resolve().parent


def check(config):
    geometry = geometry_check()
    p = parameters(config)
    cameras = camera_plan(config["candidate_id"])
    if [(c["width"], c["height"]) for c in cameras] != [(1920,1080)] + [(1280,720)] * 3:
        raise ValueError("Four-view capture profile changed")
    return {"offline_geometry": geometry, "case_id": config["case_id"],
            "candidate_id": config["candidate_id"], "route_points": len(p["native_route_xy_m"]),
            "native_imported": False, "physical_success_claimed": False}


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, allow_nan=False, indent=2)
        stream.write("\n")


def body_xy(actor):
    pose = actor.get_transform()
    return [list(v) for v in sorted({(round(v.x,5),round(v.y,5))
            for v in actor.bounding_box.get_world_vertices(pose)})]


def observed_speed_mps(actor):
    v = actor.get_velocity()
    if not all(math.isfinite(a) for a in (v.x,v.y,v.z)):
        raise ValueError("Nonfinite observed Native velocity")
    return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)


def camera_transform(carla, spec):
    x,y,z = spec["xyz_m"]
    if spec["attachment"] == "world":
        yaw = math.degrees(math.atan2(-y,-x))
        pitch = math.degrees(math.atan2(-z, math.hypot(x,y)))
    else:
        yaw,pitch = 0,spec["pitch_deg"]
    return carla.Transform(carla.Location(x=x,y=y,z=z), carla.Rotation(yaw=yaw,pitch=pitch))


def map_survey(carla, mapping, radius):
    probes = [(-30,1.75,1),(0,1.75,2),(5, -(radius-(radius+1.75)*math.cos(5/(radius+1.75))),2)]
    rows = []
    for x,y,road_id in probes:
        waypoint = mapping.get_waypoint(carla.Location(x=x,y=y,z=3),
            project_to_road=False,lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != road_id:
            raise RuntimeError("Native hill-crest lane link survey failed")
        rows.append({"xy_native_m":[x,y],"road_id":waypoint.road_id,
                     "lane_id":waypoint.lane_id,"heading_deg":waypoint.transform.rotation.yaw})
    if rows[0]["lane_id"] != rows[1]["lane_id"] or rows[1]["lane_id"] != rows[2]["lane_id"]:
        raise RuntimeError("Native route lane continuity failed")
    return rows


def execute(config, output_dir, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output/"config.json").is_file():
        raise ValueError("Use a newly materialized exact-case output directory")
    p = parameters(config)
    client = carla.Client(host,int(port)); client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved["settings"].synchronous_mode or [a for a in old.get_actors()
            if a.type_id.startswith(("vehicle.","walker.","sensor.","controller."))]:
        raise RuntimeError("Requires exclusive idle asynchronous world ownership")
    owned=[]; encoders={}; logs={}; queues={}; channels={}
    capture=None; changed=False; frames=0; error=None; restored=None
    try:
        world=client.generate_opendrive_world(open_drive(p["radius_m"]),
            carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,
                wall_height=0,additional_width=0,smooth_junctions=False,
                enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings(); settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05; settings.substepping=True
        settings.max_substep_delta_time=.01; settings.max_substeps=10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map()
        native_hash=hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()
        survey=map_survey(carla,mapping,p["radius_m"])
        write_new(output/"road_geometry.json",{"native_map_sha256":native_hash,
            "authored_map_sha256":config["native_request"]["map_sha256"],
            "lane_survey":survey,"turn_entry_x_m":0,"area_classification":p["area"]})
        ego_bp=world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        ego_bp.set_attribute("role_name","c104393_ego")
        ego=world.spawn_actor(ego_bp,carla.Transform(
            carla.Location(x=-130,y=1.75,z=.5),carla.Rotation(yaw=0)))
        owned.append(ego)
        other_bp=world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        other_bp.set_attribute("role_name","c104393_opposing")
        other=world.spawn_actor(other_bp,carla.Transform(
            carla.Location(x=-30,y=-1.75,z=1.5),carla.Rotation(yaw=180)))
        owned.append(other)
        other.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        for _ in range(40):world.tick()
        initial=body_xy(ego)
        if not all(0<y<3.5 for x,y in initial):
            raise RuntimeError("Initial Native ego body leaves surveyed approach lane")
        physics=ego.get_physics_control()
        if len(physics.wheels)!=4:raise RuntimeError("Native wheel geometry missing")
        wheelbase=(max(w.position.x for w in physics.wheels)-min(w.position.x for w in physics.wheels))/100
        max_steer=max(w.max_steer_angle for w in physics.wheels)
        controller=PathController(p["native_route_xy_m"],wheelbase,max_steer,p["controller_knobs"])
        write_new(output/"native-construction-context.json",{
            "case_id":config["case_id"],"candidate_id":config["candidate_id"],
            "native_map_sha256":native_hash,"ego_blueprint":ego.type_id,
            "other_blueprint":other.type_id,"wheelbase_m":wheelbase,
            "max_steer_deg":max_steer,"initial_body_xy_native_m":initial,
            "controller_knobs":vars(p["controller_knobs"]),
            "signal_onset_x_m":p["signal_start_x_m"],
            "requested_signal_distance_ft":p["signal_start_ft"],
            "physical_success_claimed":False})
        for spec in camera_plan(config["candidate_id"]):
            bp=world.get_blueprint_library().find("sensor.camera.rgb")
            for key,value in (("image_size_x",spec["width"]),("image_size_y",spec["height"]),
                              ("fov",spec["fov_deg"]),("sensor_tick",0)):
                bp.set_attribute(key,str(value))
            camera=world.spawn_actor(bp,camera_transform(carla,spec),
                attach_to=ego if spec["attachment"]=="ego" else None)
            owned.append(camera); queues[spec["name"]]=queue.Queue()
            camera.listen(queues[spec["name"]].put)
            logs[spec["name"]]=(output/(spec["name"]+".encoder.log")).open("x")
            encoders[spec["name"]]=subprocess.Popen(["ffmpeg","-nostdin","-hide_banner",
                "-loglevel","error","-n","-f","rawvideo","-pix_fmt","rgb24",
                "-s",f'{spec["width"]}x{spec["height"]}',"-r","20","-i","pipe:0",
                "-an","-c:v","ffv1",str(output/(spec["name"]+".mkv"))],
                stdin=subprocess.PIPE,stderr=logs[spec["name"]])
        capture=PipelineCapture(client,ego,output,config["case_id"],
            visibility=False,required_observations=config["required_atoms"])
        (output/"channels").mkdir()
        for name in config["mandatory_channels"]:
            channels[name]=(output/"channels"/(name+".jsonl")).open("x")
        start=world.get_snapshot().timestamp.elapsed_seconds
        change_seen=False
        with (output/"native_samples.jsonl").open("x") as samples, \
             (output/"video_frames.jsonl").open("x") as joins, \
             (output/"body_history.jsonl").open("x") as bodies:
            for index in range(config["duration_s"]*config["rate_hz"]):
                before=ego.get_transform(); speed=observed_speed_mps(ego)
                command=controller.step(position_xy_m=(before.location.x,before.location.y),
                    yaw_rad=math.radians(before.rotation.yaw),speed_mps=speed,dt_s=.05)
                requested=left_signal_requested(before.location.x,p["signal_start_x_m"])
                ego.set_light_state(carla.VehicleLightState.LeftBlinker if requested
                                    else carla.VehicleLightState(0))
                ego.apply_control(carla.VehicleControl(throttle=command["throttle"],
                    brake=command["brake"],steer=command["steer"],
                    hand_brake=command["hand_brake"]))
                other_speed=observed_speed_mps(other)
                other.apply_control(carla.VehicleControl(throttle=.32 if other_speed<4 else 0,
                    brake=.2 if other_speed>4.5 else 0,steer=0))
                frame=world.tick(); time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                pose=ego.get_transform(); footprint=body_xy(ego)
                observed_speed=observed_speed_mps(ego)
                changed_now=not change_seen and pose.rotation.yaw<=-1
                change_seen=change_seen or changed_now
                bits=int(ego.get_light_state()); left_bit=int(carla.VehicleLightState.LeftBlinker)
                row={"frame":index,"native_frame":frame,"video_frame":index,"time_s":time_s,
                    "ego_xy_m":[pose.location.x,pose.location.y],"native_center_xy_m":[pose.location.x,pose.location.y],
                    "heading_deg":pose.rotation.yaw,"speed_mps":observed_speed,
                    "course_change":changed_now,"signal":"left" if bits&left_bit else "off",
                    "light_state_bits":bits,"signal_requested":requested,
                    "native_body_xy_m":footprint,"route_error_m":command["route_error_m"],
                    "other_xy_m":[other.get_transform().location.x,other.get_transform().location.y],
                    "area":p["area"],"weather":p["weather"],"controller_request":command}
                capture.capture(frame,time_s,extra={"c104393_native":row})
                samples.write(json.dumps(row,allow_nan=False)+"\n")
                bodies.write(json.dumps({"frame":frame,"time_s":time_s,
                    "ego_body_xy_m":footprint},allow_nan=False)+"\n")
                values={"sig.turn_indicator":{"requested":requested,"observed":bool(bits&left_bit)},
                    "drv.distance_while":row,"kin.path_length":row,
                    "drv.turning":{"heading_deg":pose.rotation.yaw,"course_change":changed_now},
                    "env.precipitation":{"native_weather":str(world.get_weather())},
                    "kin.speed":observed_speed,"native_body_pose_control":row,
                    "camera_frame_join":{"native_frame":frame,"video_frame":index}}
                for name,stream in channels.items():
                    stream.write(json.dumps({"time_s":time_s,"value":values[name]},allow_nan=False)+"\n")
                for spec in camera_plan(config["candidate_id"]):
                    image=queues[spec["name"]].get(timeout=30)
                    while image.frame<frame:image=queues[spec["name"]].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError("Camera/Native frame join failed")
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        spec["height"],spec["width"],4)[:,:,:3][:,:,::-1]
                    encoders[spec["name"]].stdin.write(rgb.tobytes())
                joins.write(json.dumps({"video_frame":index,"native_frame":frame,
                    "carla_frame":frame,"time_s":time_s})+"\n")
                frames+=1
    except BaseException as exc:
        error={"type":type(exc).__name__,"message":str(exc),"traceback":traceback.format_exc()}
    finally:
        for stream in channels.values():stream.close()
        if capture is not None:
            try:capture.close(confirmed=error is None)
            except BaseException as exc:error=error or {"capture_close_error":str(exc)}
        for name,encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180)!=0:raise RuntimeError("Encoder failed: "+name)
            except BaseException as exc:error=error or {"encoder_error":str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {"actor_cleanup_error":str(exc)}
        if changed:
            try:restored=restore(client,saved)
            except BaseException as exc:error=error or {"world_restore_error":str(exc)}
        write_new(output/"native-capture-report.json",{"case_id":config["case_id"],
            "candidate_id":config["candidate_id"],"frames":frames,
            "expected_frames":config["duration_s"]*config["rate_hz"],"restoration":restored,
            "error":error,"accepted":False,
            "required_saved_checks":["original Native map and body containment",
                "continuous original indicator and measured path distance",
                "full video frame joins and independent pixel review"]})
    if error:raise RuntimeError("Native capture failed; inspect native-capture-report.json")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port",type=int)
    args=parser.parse_args()
    config=json.loads((ROOT/"config.json").read_text())
    if args.check:
        print(json.dumps(check(config),allow_nan=False))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error("Supply exact output directory, host and port")
        execute(config,args.output_dir,args.host,args.port)


if __name__=="__main__":
    main()
