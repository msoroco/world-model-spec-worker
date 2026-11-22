"""Original CARLA acquisition for standing, passage and two-sided sight attempts."""
from __future__ import annotations

import json
import math
import os
import queue
import shutil
import subprocess
from pathlib import Path

from native_construction import (RATE_HZ, occluder_probes, sample, sha,
                                 spawn_scene, validate_scene)


def write(path, value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")


class Cameras:
    """Four frame-joined original videos, including both statutory approaches."""
    SPECS=(("overview",1920,1080),("approach",1280,720),
           ("reference_corner",1280,720),("driver_reference",1280,720))

    def __init__(self,world,scene,output,carla):
        self.sensors=[];self.encoders={};self.queues={};self.errors=[];self.closed=False
        try:self._start(world,scene,Path(output),carla)
        except BaseException:
            self.close();raise

    def _start(self,world,scene,output,carla):
        target=(sum(scene["standing_body_xy_m"][i] for i in (0,2))/2,
                sum(scene["standing_body_xy_m"][i] for i in (1,3))/2,1.)
        distance=60.96
        positions={"overview":(0.,0.,35.),
                   "approach":(-distance,scene["sight_eye_y_m"],1.2),
                   "reference_corner":(distance,scene["sight_eye_y_m"],1.2),
                   "driver_reference":(-12.,2.2,7.)}
        library=world.get_blueprint_library()
        for name,width,height in self.SPECS:
            bp=library.find("sensor.camera.rgb")
            if bp is None:raise ValueError("Native RGB camera blueprint missing")
            for key,value in (("image_size_x",width),("image_size_y",height),("fov",75)):
                bp.set_attribute(key,str(value))
            x,y,z=positions[name]
            dx,dy,dz=target[0]-x,target[1]-y,target[2]-z
            yaw=math.degrees(math.atan2(dy,dx))
            pitch=math.degrees(math.atan2(dz,math.hypot(dx,dy)))
            sensor=world.spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=z),
                                                       carla.Rotation(pitch=pitch,yaw=yaw)))
            if sensor is None:raise RuntimeError("Native camera spawn failed: "+name)
            self.sensors.append(sensor)
            frames=queue.Queue(maxsize=4);self.queues[name]=frames
            def receive(image,q=frames,label=name):
                try:q.put_nowait(image)
                except queue.Full:self.errors.append("camera overflow: "+label)
            sensor.listen(receive)
            process=subprocess.Popen(["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-n",
                "-f","rawvideo","-pixel_format","bgra","-video_size",f"{width}x{height}",
                "-framerate",str(RATE_HZ),"-i","pipe:0","-an","-c:v","ffv1","-pix_fmt","bgra",
                str(output/(name+".mkv"))],stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
            self.encoders[name]=process

    def append(self,frame):
        if self.errors:raise RuntimeError("; ".join(self.errors))
        for name,_,_ in self.SPECS:
            image=self.queues[name].get(timeout=15)
            if image.frame!=frame:raise RuntimeError(name+" camera/world frame mismatch")
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        if self.closed:return
        self.closed=True;errors=[]
        for sensor in reversed(self.sensors):
            try:sensor.stop()
            except BaseException as exc:errors.append(repr(exc))
        for name,process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:process.stdin.close()
                if process.wait(timeout=180)!=0:errors.append("encoder failed: "+name)
            except BaseException as exc:errors.append(repr(exc))
        for sensor in reversed(self.sensors):
            try:sensor.destroy()
            except BaseException as exc:errors.append(repr(exc))
        if errors:raise RuntimeError("; ".join(errors))


def run_native(scene,output,host,port,map_source,scene_path):
    # Keep imported pipeline module side effects within a worker scratch root.
    root=Path(__file__).resolve().parents[2]
    safe_root=(root/".runtime-work").resolve()
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]=str(safe_root/"c135705-native-runtime")
    if not Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve().is_relative_to(safe_root):
        raise ValueError("pipeline output root must be under .runtime-work")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import fields,equal

    validate_scene(scene,map_source)
    output=Path(output).resolve()
    if not output.is_dir() or not output.is_relative_to(safe_root):
        raise ValueError("fresh Native attempt directory under .runtime-work required")
    if any((output/name).exists() for name in ("trace.jsonl","video_frames.jsonl",
                                              "capture-seal.json","standing-body-history.jsonl")):
        raise ValueError("Native attempt already contains original acquisition")
    client=carla.Client(host,port);client.set_timeout(30)
    old_world=client.get_world();old_map=old_world.get_map().name
    if not old_map or old_map.startswith("OpenDriveMap"):
        raise ValueError("original world needs a loadable CARLA map for restoration")
    old_settings=old_world.get_settings()
    world=None;actors=[];cameras=capture=frame_map=None
    frames=[];phase="initializing";error=None;restored=False
    try:
        source=Path(map_source)
        if sha(source)!=scene["map_source_sha256"]:raise ValueError("authored map changed")
        if not (output/"construction.json").is_file() or not (output/"runner.py").is_file():
            raise ValueError("runtime materialized construction and runner required")
        if Path(scene_path).resolve()!=output/"scene.json":
            raise ValueError("Native scene must be materialized in the attempt")
        shutil.copyfile(source,output/"authored-road.xodr")
        world=client.generate_opendrive_world(source.read_text())
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        standing,passing,props,actors=spawn_scene(world,scene,carla)
        write(output/"acquisition-provenance.json",{
            "provenance_kind":"native","diagnostic_fixture":False,
            "method":"original CARLA live acquisition from source-hashed worker OpenDRIVE",
            "authored_road_sha256":sha(output/"authored-road.xodr")})
        write(output/"occluder-live-initial.json",occluder_probes(scene,props))
        cameras=Cameras(world,scene,output,carla)
        capture=PipelineCapture(client,standing,output,scene["case_id"])
        frame_map=FrameMap(output/"video_frames.jsonl")
        phase="capturing"
        with (output/"standing-body-history.jsonl").open("x",buffering=1) as standing_file,\
             (output/"passing-body-history.jsonl").open("x",buffering=1) as passing_file,\
             (output/"occluder-body-history.jsonl").open("x",buffering=1) as props_file,\
             (output/"mechanical-attempt-history.jsonl").open("x",buffering=1) as mechanism_file:
            for index in range(round(scene["duration_s"]*RATE_HZ)):
                # The requested constant velocity is a controller command; the
                # measured original pose/velocity/body is retained independently.
                passing.set_target_velocity(carla.Vector3D(x=-16.0,y=0.,z=0.))
                frame=world.tick();snapshot=world.get_snapshot()
                if frame!=snapshot.frame:raise RuntimeError("Native world frame mismatch")
                time_s=snapshot.timestamp.elapsed_seconds
                capture.capture(frame,time_s)
                cameras.append(frame)
                frame_map.append(frame,time_s)
                standing_file.write(json.dumps(sample(standing,snapshot),allow_nan=False)+"\n")
                passing_file.write(json.dumps(sample(passing,snapshot),allow_nan=False)+"\n")
                props_file.write(json.dumps({"frame":frame,"time_s":time_s,
                    "actors":[sample(prop,snapshot) for prop in props]},allow_nan=False)+"\n")
                mechanism_file.write(json.dumps({"frame":frame,"time_s":time_s,
                    "standing_actor_id":int(standing.id),"engine_disabled_by_worker":True,
                    "physics_disabled_by_worker":True,"brake_requested":1.,
                    "hand_brake_requested":True,"duration_since_first_sample_s":index/RATE_HZ,
                    "unavoidable_stop_verified":False},allow_nan=False)+"\n")
                frames.append(frame)
        phase="closing"
        capture.close();capture=None
        frame_map.close();frame_map=None
        cameras.close();cameras=None
        names=("scene.json","trace.jsonl","video_frames.jsonl","road.xodr","authored-road.xodr",
               "carla_recorder.log","standing-body-history.jsonl","passing-body-history.jsonl",
               "occluder-body-history.jsonl","mechanical-attempt-history.jsonl",
               "occluder-live-initial.json",*(name+".mkv" for name,_,_ in Cameras.SPECS))
        write(output/"acquisition.json",{name:{"kind":"original_native","sha256":sha(output/name)}
                                          for name in names})
        phase="sealed"
    except BaseException as exc:
        error=repr(exc);raise
    finally:
        cleanup=[]
        for resource in (capture,frame_map,cameras):
            if resource is not None:
                try:resource.close()
                except BaseException as exc:cleanup.append(repr(exc))
        for actor in reversed(actors):
            try:actor.destroy()
            except BaseException as exc:cleanup.append(repr(exc))
        try:
            # generate_opendrive_world changes the loaded world; reload and
            # verify the original settings before any capture can be sealed.
            restored_world=client.load_world(old_map)
            restored_world.apply_settings(old_settings)
            restored=all(equal(fields(restored_world.get_settings()).get(k),v)
                         for k,v in fields(old_settings).items())
            restored=restored and restored_world.get_map().name==old_map
        except BaseException as exc:cleanup.append(repr(exc))
        if phase=="sealed" and not cleanup and restored:
            seal_capture(output,frames=len(frames),restoration={
                "restored":True,"settings_readback":"original map and settings restored"},
                errors=[],encoder_exit_codes={name:0 for name,_,_ in Cameras.SPECS},
                context={"authored_road_sha256":sha(output/"authored-road.xodr"),
                         "case_id":scene["case_id"]})
        else:
            write(output/"native-run-status.json",{"phase":phase,"errors":[e for e in [error,*cleanup] if e],
                                                   "original_world_restored":restored})
            if phase=="sealed":raise RuntimeError("Native cleanup or world restoration failed")
