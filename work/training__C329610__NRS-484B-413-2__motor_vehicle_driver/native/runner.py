"""Proposed original Native signaling capture; not executed or accepted.

The local operator must supply an exclusively owned CARLA server. The runner
never starts a server, touches SQLite, or assigns a statutory outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import traceback

from cameras import camera_plan
from controller import EngineeringKnobs, PathController
from engineering import parameters
from geometry import check as geometry_check, open_drive
from signal_control import left_signal_requested

ROOT = Path(__file__).resolve().parent


def frame_map_row(index,frame,time_s):
    """Preserve both Native and canonical CARLA identities for saved/Core joins."""
    if type(index) is not int or index<0 or type(frame) is not int or frame<0:
        raise ValueError("Invalid original video/Native frame identity")
    if isinstance(time_s,bool) or not isinstance(time_s,(int,float)) or not math.isfinite(time_s):
        raise ValueError("Invalid original video/Native time")
    return {"video_frame":index,"native_frame":frame,"carla_frame":frame,"time_s":time_s}


def write_new(path, value):
    with path.open("x") as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.write("\n")


def check(config):
    geometry = geometry_check()
    candidate = config["candidate_id"]
    if config["case_id"].split("__")[-1] not in (
            "below_100_ft","at_100_ft","above_100_ft","below_300_ft","at_300_ft","above_300_ft") or candidate not in ("primary","fallback1","fallback2","fallback3"):
        raise ValueError("Unknown selected case or construction")
    if config["duration_s"] != 40 or config["rate_hz"] != 20:
        raise ValueError("Capture rate/duration differs from plan")
    parameters(config)
    cameras=camera_plan(candidate)
    if [(c["width"],c["height"]) for c in cameras] != [(1920,1080),(1280,720),(1280,720),(1280,720)]:
        raise ValueError("Four-view profile changed")
    return {"offline_geometry":geometry,"candidate_id":candidate,
            "camera_profile":"overview1080-capability-v1","native_imported":False,
            "physical_success_claimed":False}


def body_xy(actor):
    transform=actor.get_transform()
    vertices=actor.bounding_box.get_world_vertices(transform)
    projected=sorted({(round(v.x,5),round(v.y,5)) for v in vertices})
    if len(projected)!=4:
        raise RuntimeError("Native body does not yield four horizontal footprint vertices")
    return [list(v) for v in projected]


def direction(waypoint):
    v=waypoint.transform.get_forward_vector()
    length=math.hypot(v.x,v.y)
    if length < .99:
        raise RuntimeError("Native lane has no horizontal direction")
    return [v.x/length,v.y/length]


def map_survey(carla, mapping, native_hash):
    requests={"approach_forward":(-30,1.75,1,[1,0]),
              "approach_opposing":(-30,-1.75,1,[-1,0]),
              "destination_forward":(1.75,-30,4,[0,-1]),
              "destination_opposing":(-1.75,-30,4,[0,1])}
    observed={}
    for name,(x,y,road_id,expected) in requests.items():
        wp=mapping.get_waypoint(carla.Location(x=x,y=y,z=.2),project_to_road=False,lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id!=road_id:
            raise RuntimeError("Native lane survey failed: "+name)
        vector=direction(wp)
        if sum(a*b for a,b in zip(vector,expected))<.98:
            raise RuntimeError("Native lane direction differs from authored road: "+name)
        observed[name]=vector
    return {"native_map_sha256":native_hash,"road_directions_native":observed,
            "approach_centerline_point_native_m":[0,0],
            "approach_right_normal_native":[0,1],"right_half_width_m":7,
            "intersection_entry_point_native_m":[-7,0],
            "approach_forward_native":observed["approach_forward"],
            "destination_exit_point_native_m":[0,-7],
            "destination_forward_native":observed["destination_forward"],
            "intersection_polygon_xy_m":[[-7,-7],[7,-7],[7,7],[-7,7]],
            "boundary_provenance":"Authored roadway edge/centerline from Native map readback; visual and physical survey still required"}


def camera_transform(carla, spec):
    x,y,z=spec["xyz_m"]
    if spec["attachment"]=="world":
        dx,dy,dz=-x,-y,-z
        yaw=math.degrees(math.atan2(dy,dx))
        pitch=math.degrees(math.atan2(dz,math.hypot(dx,dy)))
    else:
        yaw=0
        pitch=spec["pitch_deg"]
    return carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(pitch=pitch,yaw=yaw))


def execute(config, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore
    check(config)
    output=Path(output).resolve()
    if not output.is_dir() or not (output/"config.json").is_file():
        raise ValueError("Use a new materialized exact-case output directory")
    client=carla.Client(host,int(port));client.set_timeout(180)
    saved=snapshot(client)
    prior_world=client.get_world()
    if saved["settings"].synchronous_mode or [a for a in prior_world.get_actors()
        if a.type_id.startswith(("vehicle.","walker.","sensor.","controller."))]:
        raise RuntimeError("Requires exclusive idle asynchronous world ownership")
    owned=[];encoders={};encoder_logs={};camera_queues={};channels={}
    capture=None;changed=False;error=None;frames=0;restored=None
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map();native_xml=mapping.to_opendrive()
        native_hash=hashlib.sha256(native_xml.encode()).hexdigest()
        survey=map_survey(carla,mapping,native_hash)
        engineering=parameters(config)
        survey["authored_map_sha256"]=config["native_request"]["map_sha256"]
        survey["area_classification"]=engineering["area"]
        write_new(output/"road_geometry.json",survey)
        write_new(output/"context.json",{'surveyed_two_way_intersection':survey})
        candidate=config["candidate_id"]
        lateral=-1.75
        blueprint=world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        blueprint.set_attribute("role_name","c329610_ego")
        ego=world.spawn_actor(blueprint,carla.Transform(carla.Location(x=engineering["start_x_m"],y=-lateral,z=.5),carla.Rotation(yaw=0)))
        owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        for _ in range(40):world.tick()
        initial=body_xy(ego)
        if not all(0<y<7 for x,y in initial):
            raise RuntimeError("Actual Native vehicle footprint not contained in right half at start")
        physics=ego.get_physics_control()
        wheels=physics.wheels
        if len(wheels)!=4:raise RuntimeError("Native blueprint wheel geometry unverified")
        wheelbase=(max(w.position.x for w in wheels)-min(w.position.x for w in wheels))/100
        max_steer=max(w.max_steer_angle for w in wheels)
        native_route=engineering["native_route_xy_m"]
        knobs=engineering["controller_knobs"]
        controller=PathController(native_route,wheelbase,max_steer,knobs)
        write_new(output/"native-construction-context.json",{
            "case_id":config["case_id"],"candidate_id":candidate,"map_sha256":native_hash,
            "vehicle_blueprint":ego.type_id,"wheelbase_m":wheelbase,"max_steer_deg":max_steer,
            "initial_body_xy_native_m":initial,"controller_knobs":vars(knobs),
            "authored_intent":"left turn with continuous preturn signal; separate from observed motion",
            "signal_onset_x_m":engineering["signal_onset_x_m"],
            "target_signal_distance_ft":engineering["target_signal_distance_ft"],
            "area_classification":engineering["area"],
            "native_route_points":len(native_route),"physical_success_claimed":False})
        for spec in camera_plan(candidate):
            camera_bp=world.get_blueprint_library().find("sensor.camera.rgb")
            for key,value in (("image_size_x",spec["width"]),("image_size_y",spec["height"]),
                              ("fov",spec["fov_deg"]),("sensor_tick",0)):
                camera_bp.set_attribute(key,str(value))
            camera=world.spawn_actor(camera_bp,camera_transform(carla,spec),
                attach_to=ego if spec["attachment"]=="ego" else None)
            owned.append(camera)
            camera_queues[spec["name"]]=queue.Queue()
            camera.listen(camera_queues[spec["name"]].put)
            encoder_logs[spec["name"]]=(output/(spec["name"]+".encoder.log")).open("x")
            encoders[spec["name"]]=subprocess.Popen([
                "ffmpeg","-nostdin","-hide_banner","-loglevel","error","-n",
                "-f","rawvideo","-pix_fmt","rgb24","-s",f'{spec["width"]}x{spec["height"]}',
                "-r","20","-i","pipe:0","-an","-c:v","ffv1","-level","1",
                str(output/(spec["name"]+".mkv"))],stdin=subprocess.PIPE,stderr=encoder_logs[spec["name"]])
        capture=PipelineCapture(client,ego,output,config["case_id"],
            visibility=False,required_observations=config.get("required_atoms",[]))
        (output/"channels").mkdir()
        for name in config["mandatory_channels"]:
            channels[name]=(output/"channels"/(name+".jsonl")).open("x")
        start=world.get_snapshot().timestamp.elapsed_seconds
        course_change_seen=False
        with (output/"native_samples.jsonl").open("x") as native_file, \
             (output/"body_history.jsonl").open("x") as body_file, \
             (output/"video_frames.jsonl").open("x") as frame_file:
            for index in range(config["duration_s"]*config["rate_hz"]):
                before=ego.get_transform();velocity=ego.get_velocity()
                speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                command=controller.step(position_xy_m=(before.location.x,before.location.y),
                    yaw_rad=math.radians(before.rotation.yaw),speed_mps=speed,dt_s=.05)
                signal_requested=left_signal_requested(before.location.x,engineering["signal_onset_x_m"])
                ego.set_light_state(carla.VehicleLightState.LeftBlinker if signal_requested
                                    else carla.VehicleLightState(0))
                ego.apply_control(carla.VehicleControl(throttle=command["throttle"],
                    brake=command["brake"],steer=command["steer"],
                    hand_brake=command["hand_brake"]))
                frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                pose=ego.get_transform();forward=pose.get_forward_vector();body=body_xy(ego)
                course_change_now=not course_change_seen and pose.rotation.yaw <= -1
                course_change_seen=course_change_seen or course_change_now
                light_bits=int(ego.get_light_state())
                left_bit=int(carla.VehicleLightState.LeftBlinker)
                sample={"time_s":time_s,"native_frame":frame,
                    "video_frame":index,"frame":index,
                    "native_center_xy_m":[pose.location.x,pose.location.y],
                    "ego_xy_m":[pose.location.x,pose.location.y],
                    "heading_deg":pose.rotation.yaw,
                    "course_change":course_change_now,
                    "signal":"left" if light_bits & left_bit else "off",
                    "native_forward_xy":[forward.x/math.hypot(forward.x,forward.y),
                                         forward.y/math.hypot(forward.x,forward.y)],
                    "native_body_xy_m":body,"speed_mps":speed,
                    "area":engineering["area"],"weather":engineering["weather"],
                    "signal_requested":signal_requested,
                    "light_state_bits":light_bits,
                    "left_indicator_state_observed":bool(light_bits & left_bit),
                    "controller_request":command}
                capture.capture(frame,time_s,extra={"c329610_native":sample})
                native_file.write(json.dumps(sample,allow_nan=False)+"\n")
                body_file.write(json.dumps({"frame":frame,"time_s":time_s,
                    "body_vertices_m":[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(pose)]},
                    allow_nan=False)+"\n")
                values={"drv.turning":{"authored_intent":"left turn","observed_heading_deg":pose.rotation.yaw},
                    "sig.turn_indicator":{"requested":signal_requested,"observed_left_indicator_state":bool(light_bits & left_bit),"light_state_bits":light_bits},
                    "drv.distance_while":{"signal_start_station_x_m":engineering["signal_onset_x_m"],"observed_pose_xy_m":sample["native_center_xy_m"]},
                    "kin.path_length":{"route_station_m":command["route_station_m"],"observed_pose_xy_m":sample["native_center_xy_m"]},
                    "env.precipitation":{"authored_weather":engineering["weather"],"native_weather":str(world.get_weather())},
                    "kin.speed":speed,
                    "st.intersection":survey,"st.lane_enters":survey,
                    "st.centre_line":survey["approach_centerline_point_native_m"],
                    "rel.occupies":body,"kin.position":sample["native_center_xy_m"],
                    "st.one_way_roadway":survey["road_directions_native"],
                    "st.lane_direction":survey["road_directions_native"],
                    "native_body_pose_control":sample,
                    "camera_frame_join":{"native_frame":frame,"video_frame":index}}
                for name,stream in channels.items():
                    stream.write(json.dumps({"time_s":time_s,"value":values[name]},allow_nan=False)+"\n")
                for spec in camera_plan(candidate):
                    image=camera_queues[spec["name"]].get(timeout=30)
                    while image.frame<frame:image=camera_queues[spec["name"]].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError("Original camera/Native frame join failed")
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(spec["height"],spec["width"],4)[:,:,:3][:,:,::-1]
                    encoders[spec["name"]].stdin.write(rgb.tobytes())
                frame_file.write(json.dumps(frame_map_row(index,frame,time_s))+"\n")
                frames+=1
        if frames!=config["duration_s"]*config["rate_hz"]:
            raise RuntimeError("Original frame count incomplete")
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
                if encoder.wait(timeout=180)!=0:raise RuntimeError("Lossless encoder failed: "+name)
            except BaseException as exc:error=error or {"encoder_error":str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {"owned_actor_cleanup_error":str(exc)}
        if changed:
            try:restored=restore(client,saved)
            except BaseException as exc:error=error or {"world_restore_error":str(exc)}
        write_new(output/"native-capture-report.json",{
            "case_id":config["case_id"],"candidate_id":config["candidate_id"],
            "frames":frames,"expected_frames":config["duration_s"]*config["rate_hz"],
            "restoration":restored,"error":error,"accepted":False,
            "required_saved_checks":["actual original pixels","Native body and lane joins",
                "exact full video/trace frame mapping","measured turn completion","independent audit"]})
    if error:raise RuntimeError("Native attempt failed; see native-capture-report.json: "+str(error))


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
            parser.error("Supply materialized output directory, host and port")
        execute(config,args.output_dir,args.host,args.port)


if __name__=="__main__":
    main()
