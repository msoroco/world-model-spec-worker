"""Original-footprint observations for NRS 484B.400(5); no legal cutoff."""
from __future__ import annotations
from math import atan2, cos, degrees, hypot, isfinite, radians, sin
import json
import hashlib
from pathlib import Path

def _load(p):
    p=Path(p)
    if not p.is_file(): raise ValueError("missing required geometry source: "+str(p))
    return json.loads(p.read_text())

def _line(points):
    if not isinstance(points,list) or len(points)!=2: raise ValueError("line needs two original map points")
    a,b=points
    if any(type(v) not in (int,float) or not isfinite(v) for p in points for v in p) or len(a)!=2 or len(b)!=2:
        raise ValueError("invalid map point")
    dx,dy=b[0]-a[0],b[1]-a[1]
    length=hypot(dx,dy)
    if length < 1: raise ValueError("degenerate map reference line")
    return a,dx,dy,length

def _signed(point,line):
    a,dx,dy,length=line
    return (dx*(point[1]-a[1])-dy*(point[0]-a[0]))/length

def measure(geometry_path, body_path):
    g,b=_load(geometry_path),_load(body_path)
    if g.get("source_directionality")!="one_way" or g.get("destination_directionality")!="one_way":
        raise ValueError("exact one-way-to-one-way layout missing")
    if g.get("maneuver")!="left_turn" or not g.get("intersection_id") or not g.get("map_source"):
        raise ValueError("turn or map-source provenance missing")
    curb=_line(g.get("source_left_curb")); destination_curb=_line(g.get("destination_left_curb"))
    rows=b.get("frames")
    if not isinstance(rows,list) or not rows: raise ValueError("original body footprint frames missing")
    indices=[r.get("frame") for r in rows]
    if any(type(i) is not int for i in indices) or indices!=sorted(set(indices)):
        raise ValueError("body frame identities unordered or repeated")
    if not b.get("subject_id") or any(r.get("subject_id")!=b["subject_id"] for r in rows):
        raise ValueError("body footprint subject mismatch")
    approach=[r for r in rows if r.get("phase")=="approach"]
    departure=[r for r in rows if r.get("phase")=="leaving_intersection"]
    if not approach or not departure or approach[-1]["frame"]>=departure[0]["frame"]:
        raise ValueError("approach and leaving-intersection phases absent or reversed")
    def corners(row):
        p=row.get("ground_corners")
        if not isinstance(p,list) or len(p)!=4 or any(not isinstance(x,list) or len(x)!=2 or any(type(v) not in (int,float) or not isfinite(v) for v in x) for x in p):
            raise ValueError("four original ground body corners required")
        return p
    approach_curb=[abs(_signed(p,curb)) for r in approach for p in corners(r)]
    departure_curb=[abs(_signed(p,destination_curb)) for r in departure for p in corners(r)]
    return {"subject_id":b["subject_id"],"intersection_id":g["intersection_id"],
            "source_directionality":"one_way","destination_directionality":"one_way",
            "maneuver":"left_turn","approach_left_curb_nearest_m":min(approach_curb),
            "approach_left_curb_farthest_m":max(approach_curb),
            "departure_left_curb_nearest_m":min(departure_curb),
            "departure_left_curb_farthest_m":max(departure_curb),
            "approach_frame_ids":[r["frame"] for r in approach],
            "departure_frame_ids":[r["frame"] for r in departure],
            "source_refs":[str(geometry_path),str(body_path)],
            "source_sha256":{str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest()
                             for p in (geometry_path,body_path)},
            "legal_conclusion":None}

def construct_route_targets(geometry_path, approach_offset_m, departure_offset_m):
    """Plan two independently controlled left-curb offsets from original map readback.

    These are controller targets, never an assertion of realized motion or legal
    practicability. The source must supply the inward side and available width
    for both one-way highways, so this function cannot guess a map orientation.
    """
    path=Path(geometry_path)
    g=_load(path)
    if (g.get("source_directionality"),g.get("destination_directionality"),g.get("maneuver")) != ("one_way","one_way","left_turn"):
        raise ValueError("exact one-way-to-one-way left-turn layout missing")
    if not g.get("map_source") or not g.get("intersection_id"):
        raise ValueError("original map provenance or intersection identity missing")
    targets={}
    for name,offset in (("source",approach_offset_m),("destination",departure_offset_m)):
        curb=_line(g.get(name+"_left_curb"))
        normal=g.get(name+"_left_curb_inward_unit")
        width=g.get(name+"_road_width_m")
        if (type(offset) not in (int,float) or type(width) not in (int,float)
                or not isfinite(offset) or not isfinite(width)
                or not 0 < offset < width):
            raise ValueError("curb offset outside source road width: "+name)
        if (not isinstance(normal,list) or len(normal)!=2
                or any(type(v) not in (int,float) or not isfinite(v) for v in normal)
                or abs(hypot(*normal)-1)>.001
                or abs(normal[0]*curb[1]+normal[1]*curb[2])>.001):
            raise ValueError("source inward curb normal missing or not perpendicular: "+name)
        a,dx,dy,_=curb
        targets[name]={"left_curb_offset_setpoint_m":float(offset),
                       "waypoints_xy_m":[[a[0]+t*dx+offset*normal[0],
                                          a[1]+t*dy+offset*normal[1]]
                                         for t in (.2,.8)]}
    return {"intersection_id":g["intersection_id"],"map_source":g["map_source"],
            "geometry_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "approach":targets["source"],"departure":targets["destination"],
            "actual_native_motion_verified":False,"legal_conclusion":None}

def native_route_plan(geometry_path, branch):
    """Build a map-bound engineering route for one of the three selected cases."""
    offsets={"approach_near_depart_near":(.5,.5),
             "approach_far_depart_near":(1.5,.5),
             "approach_near_depart_far":(.5,1.5)}
    if branch not in offsets:raise ValueError("unknown selected one-way turn branch")
    g=_load(geometry_path)
    route=construct_route_targets(geometry_path,*offsets[branch])
    headings={}
    for name in ("source","destination"):
        curb=_line(g[name+"_left_curb"])
        direction=g.get(name+"_travel_unit")
        if (not isinstance(direction,list) or len(direction)!=2
                or any(type(v) not in (int,float) or not isfinite(v) for v in direction)
                or abs(hypot(*direction)-1)>.001
                or (direction[0]*curb[1]+direction[1]*curb[2])/curb[3]<.999):
            raise ValueError("one-way travel heading disagrees with map curb: "+name)
        headings[name]=degrees(atan2(direction[1],direction[0]))
    source_direction=g["source_travel_unit"]
    destination_direction=g["destination_travel_unit"]
    cross=(source_direction[0]*destination_direction[1]
           -source_direction[1]*destination_direction[0])
    dot=(source_direction[0]*destination_direction[0]
         +source_direction[1]*destination_direction[1])
    if cross<.7 or abs(dot)>.5:
        raise ValueError("source-to-destination route is not a left turn")
    route["branch"]=branch
    route["source_heading_deg"]=headings["source"]
    route["destination_heading_deg"]=headings["destination"]
    route["route_xy_m"]=route["approach"]["waypoints_xy_m"]+route["departure"]["waypoints_xy_m"]
    return route

def spawn_native_scene(world, carla, geometry_path, branch, vehicle_blueprint_id):
    """Spawn only after original map identity and lane directions are checked.

    The caller owns world ticks and must destroy every returned actor in a finally
    block. No CARLA import happens during CPU construction tests.
    """
    route=native_route_plan(geometry_path,branch)
    if world.get_map().name!=route["map_source"]:
        raise ValueError("CARLA map differs from original curb source")
    library=world.get_blueprint_library()
    vehicle_bp=library.find(vehicle_blueprint_id)
    x,y=route["approach"]["waypoints_xy_m"][0]
    transform=carla.Transform(carla.Location(x=x,y=y,z=.5),
                              carla.Rotation(yaw=route["source_heading_deg"]))
    ego=world.try_spawn_actor(vehicle_bp,transform)
    if ego is None:raise ValueError("one-way curb vehicle spawn failed")
    return {"ego":ego,"route":route,"actors":[ego],"camera_actors":{}}

CAMERA_TRANSFORMS={
    "overview":((-7,0,13),(-35,0,0)),
    "approach":((-7,0,3),(-10,0,0)),
    "reference_corner":((1,-3,4),(-20,0,90)),
    "driver_reference":((.15,0,1.5),(0,0,0)),
}

def spawn_native_cameras(world, carla, scene, sinks):
    """Attach four named RGB sources and route raw images to caller-owned sinks."""
    if set(sinks)!=set(CAMERA_TRANSFORMS):
        raise ValueError("four named camera sinks required")
    if scene["camera_actors"]:raise ValueError("cameras already attached")
    actors=[]
    try:
        for name,(position,rotation) in CAMERA_TRANSFORMS.items():
            bp=world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x","960")
            bp.set_attribute("image_size_y","540")
            bp.set_attribute("fov","90")
            bp.set_attribute("sensor_tick","0.05")
            transform=carla.Transform(carla.Location(*position),carla.Rotation(*rotation))
            sensor=world.spawn_actor(bp,transform,attach_to=scene["ego"])
            if sensor is None:raise ValueError("camera spawn failed: "+name)
            sensor.listen(sinks[name])
            actors.append((name,sensor))
    except Exception:
        for _,sensor in reversed(actors):sensor.destroy()
        raise
    scene["camera_actors"]={name:sensor for name,sensor in actors}
    scene["actors"].extend(sensor for _,sensor in actors)
    return scene

def apply_route_control(scene, carla, waypoint_index, target_speed_mps=4.0):
    """Steer toward a declared point using current Native pose and speed."""
    route=scene["route"]["route_xy_m"]
    if type(waypoint_index) is not int or not 0<=waypoint_index<len(route):
        raise ValueError("selected route waypoint missing")
    if type(target_speed_mps) not in (int,float) or not isfinite(target_speed_mps) or target_speed_mps<=0:
        raise ValueError("invalid engineering speed setpoint")
    ego=scene["ego"]
    pose=ego.get_transform()
    velocity=ego.get_velocity()
    x,y=route[waypoint_index]
    dx,dy=x-pose.location.x,y-pose.location.y
    if not all(isfinite(v) for v in (dx,dy,pose.rotation.yaw,velocity.x,velocity.y)):
        raise ValueError("nonfinite Native pose or velocity")
    distance=hypot(dx,dy)
    heading=radians(pose.rotation.yaw)
    error=atan2(cos(heading)*dy-sin(heading)*dx,
                cos(heading)*dx+sin(heading)*dy)
    steering=max(-.7,min(.7,1.5*error))
    speed=hypot(velocity.x,velocity.y)
    throttle=max(0.,min(.55,.2*(target_speed_mps-speed)))
    brake=max(0.,min(.5,.25*(speed-target_speed_mps)))
    ego.apply_control(carla.VehicleControl(throttle=throttle,steer=steering,brake=brake))
    return {"waypoint_index":waypoint_index,"distance_to_waypoint_m":distance,
            "steering_error_rad":error,"speed_mps":speed,"reached":distance<.75}

class FFmpegCameraSink:
    """Write each original CARLA BGRA frame as a lossless source video."""
    def __init__(self, root, name, popen=None):
        import subprocess
        if name not in CAMERAS:raise ValueError("unknown original curb camera")
        output=Path(root)/(name+".mkv")
        if output.exists():raise ValueError("retain previous camera source")
        launcher=popen or subprocess.Popen
        self.process=launcher(["ffmpeg","-nostdin","-loglevel","error","-y",
                               "-f","rawvideo","-pixel_format","bgra",
                               "-video_size","960x540","-framerate","20",
                               "-i","pipe:0","-an","-c:v","ffv1",str(output)],
                              stdin=subprocess.PIPE)
        self.closed=False
    def write(self,image):
        if self.closed or (image.width,image.height)!=(960,540) or len(image.raw_data)!=960*540*4:
            raise ValueError("original curb camera dimensions or bytes changed")
        self.process.stdin.write(image.raw_data)
    def close(self):
        if not self.closed:
            self.closed=True
            self.process.stdin.close()
            if self.process.wait()!=0:raise ValueError("original curb camera encoder failed")

class NativeCameraFrameJoin:
    """Wait for all four original images before recording one Native frame map."""
    def __init__(self, root, world, carla, scene, sink_factory=FFmpegCameraSink):
        from threading import Condition
        self.root=Path(root);self.condition=Condition();self.frames={name:set() for name in CAMERAS}
        self.errors=[];self.closed=False;self.last_frame=None;self.last_time=None;self.index=0
        self.sinks={};self.files={}
        try:
            for name in CAMERAS:
                self.sinks[name]=sink_factory(root,name)
                self.files[name]=(self.root/(name+"-frames.jsonl")).open("x",buffering=1)
            callbacks={name:(lambda image,n=name:self._on_image(n,image)) for name in CAMERAS}
            spawn_native_cameras(world,carla,scene,callbacks)
            self.scene=scene
        except BaseException:
            self.close()
            raise
    def _on_image(self,name,image):
        with self.condition:
            if self.closed:return
            try:
                if image.frame in self.frames[name]:raise ValueError("duplicate original curb camera frame")
                self.sinks[name].write(image)
                self.frames[name].add(image.frame)
            except BaseException as error:
                self.errors.append(error)
            finally:self.condition.notify_all()
    def capture_frame(self,frame,time_s,timeout_s=10):
        from time import monotonic
        if (type(frame) is not int or type(time_s) not in (int,float) or not isfinite(time_s)
                or (self.last_frame is not None and frame<=self.last_frame)
                or (self.last_time is not None and time_s<=self.last_time)):
            raise ValueError("original curb camera frame order differs")
        deadline=monotonic()+timeout_s
        with self.condition:
            while not all(frame in frames for frames in self.frames.values()):
                if self.errors:raise ValueError("original curb camera callback failed") from self.errors[0]
                if self.closed:raise ValueError("original curb camera join closed")
                remaining=deadline-monotonic()
                if remaining<=0:raise ValueError("missing one or more original curb camera frames")
                self.condition.wait(remaining)
            if self.errors:raise ValueError("original curb camera callback failed") from self.errors[0]
        row={"video_frame":self.index,"native_frame":frame,"time_s":time_s}
        for stream in self.files.values():stream.write(json.dumps(row,allow_nan=False)+"\n")
        self.last_frame=frame;self.last_time=time_s;self.index+=1
        return row
    def verify_frames(self,frames):
        expected=set(frames)
        if not expected or len(expected)!=len(frames) or self.errors:
            raise ValueError("original curb camera frame verification failed")
        for name,observed in self.frames.items():
            if observed!=expected:raise ValueError("original curb camera frame set differs: "+name)
        if self.index!=len(frames):raise ValueError("original curb camera frame map count differs")
    def close(self):
        if self.closed:return
        self.closed=True
        errors=[]
        for stream in self.files.values():
            try:stream.close()
            except BaseException as error:errors.append(str(error))
        for name,sensor in getattr(self,"scene",{}).get("camera_actors",{}).items():
            try:sensor.stop()
            except BaseException as error:errors.append(str(error))
        for sink in self.sinks.values():
            try:sink.close()
            except BaseException as error:errors.append(str(error))
        if errors:raise ValueError("original curb camera close failed: "+"; ".join(errors))

class OriginalCurbBodyCapture:
    """Retain actual bottom body corners and road phase at each joined tick."""
    def __init__(self, root, world, scene, geometry_path, pipeline_capture):
        from worker_exchange.native_output import FrameMap
        self.root=Path(root);self.world=world;self.scene=scene;self.pipeline=pipeline_capture
        geometry=_load(geometry_path)
        if world.get_map().name!=geometry.get("map_source"):
            raise ValueError("Native map differs from original curb geometry")
        source_id=geometry.get("source_road_id")
        destination_id=geometry.get("destination_road_id")
        if (type(source_id) is not int or type(destination_id) is not int
                or source_id==destination_id):
            raise ValueError("distinct original one-way road IDs required")
        self.road_ids=(source_id,destination_id)
        target=self.root/"oneway_geometry_original.json"
        if target.exists():raise ValueError("retain prior original curb geometry")
        target.write_bytes(Path(geometry_path).read_bytes())
        body=self.root/"body_ground_original.json"
        if body.exists():raise ValueError("retain prior original curb body")
        self.body_path=body;self.rows=[]
        self.frames=FrameMap(self.root/"video_frames.jsonl")
        self.closed=False
    def capture(self, frame, time_s, cameras):
        if self.closed:raise ValueError("original curb capture closed")
        if self.world.get_snapshot().frame!=frame:
            raise ValueError("body capture differs from completed Native tick")
        cameras.capture_frame(frame,time_s)
        original=self.pipeline.capture(frame,time_s)
        if (original.get("frame"),original.get("time_s"))!=(frame,time_s):
            raise ValueError("pipeline capture returned another original frame")
        ego=self.scene["ego"]
        transform=ego.get_transform()
        waypoint=self.world.get_map().get_waypoint(transform.location)
        if waypoint is None:raise ValueError("original body road waypoint missing")
        road_id=waypoint.road_id
        if waypoint.is_junction:phase="turning"
        elif road_id==self.road_ids[0]:phase="approach"
        elif road_id==self.road_ids[1]:phase="leaving_intersection"
        else:raise ValueError("original body left selected one-way road pair")
        vertices=ego.bounding_box.get_world_vertices(transform)
        if len(vertices)!=8:raise ValueError("original Native body needs eight box vertices")
        bottom=sorted(vertices,key=lambda p:p.z)[:4]
        corners=[[float(p.x),float(p.y)] for p in bottom]
        if any(not isfinite(v) for p in corners for v in p) or len({tuple(p) for p in corners})!=4:
            raise ValueError("original Native ground footprint incomplete")
        self.rows.append({"frame":frame,"time_s":time_s,"subject_id":"ego",
                          "road_id":road_id,"phase":phase,"ground_corners":corners})
        self.frames.append(frame,time_s)
        return self.rows[-1]
    def close(self):
        if self.closed:return
        self.closed=True;self.frames.close()
        if not self.rows:raise ValueError("original curb body capture empty")
        self.body_path.write_text(json.dumps({"subject_id":"ego","frames":self.rows},
                                             indent=2,allow_nan=False)+"\n")

def seal_curb_sources(attempt, case_id, *, require_decodable_media=True):
    """Hash the closed original bundle; production sealing decodes all cameras."""
    import subprocess
    root=Path(attempt)
    destination=root/"curb_source_receipt.json"
    if destination.exists():raise ValueError("original curb source receipt already exists")
    required={"oneway_geometry_original.json","body_ground_original.json",
              "trace.jsonl","video_frames.jsonl"}
    required|={name+".mkv" for name in CAMERAS}
    required|={name+"-frames.jsonl" for name in CAMERAS}
    for name in required:
        if not (root/name).is_file():raise ValueError("Missing required source: "+name)
    if require_decodable_media:
        for name in CAMERAS:
            proc=subprocess.run(["ffmpeg","-v","error","-i",str(root/(name+".mkv")),
                                 "-f","null","-"],capture_output=True)
            if proc.returncode:raise ValueError("original curb camera decode failed: "+name)
    receipt={"case_id":case_id,"source_sha256":{
        name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(required)},
             "four_camera_decode_checked":require_decodable_media,
             "physical_visibility_claimed":False}
    destination.write_text(json.dumps(receipt,indent=2,allow_nan=False)+"\n")
    return receipt

def check_native_config(config, geometry_path):
    branch=config.get("case_branch")
    route=native_route_plan(geometry_path,branch)
    case_id=config.get("selected_case_id")
    if not isinstance(case_id,str) or not case_id.endswith("__"+branch):
        raise ValueError("selected curb case and route branch differ")
    if config.get("law_id")!="NRS-484B-400-5" or config.get("cell_id")!="C152972":
        raise ValueError("frozen one-way turn law/cell differs")
    if config.get("frames")!=160 or config.get("duration_s")!=8:
        raise ValueError("exact 8 second / 20 Hz capture plan differs")
    if config.get("source_geometry_sha256")!=route["geometry_sha256"]:
        raise ValueError("source curb geometry hash differs")
    offsets=config.get("curb_offsets_m")
    if offsets!={"approach":route["approach"]["left_curb_offset_setpoint_m"],
                 "departure":route["departure"]["left_curb_offset_setpoint_m"]}:
        raise ValueError("selected curb controller offsets differ")
    if not config.get("vehicle_blueprint_id"):
        raise ValueError("Native vehicle blueprint missing")
    return route

def run_native(attempt, geometry_path, host="127.0.0.1", port=2000):
    """Prospective CARLA run; explicit invocation only, never a CPU proof claim."""
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    root=Path(attempt)
    config=_load(root/"config.json")
    route=check_native_config(config,geometry_path)
    client=carla.Client(host,port);client.set_timeout(30.)
    world=client.get_world();original=world.get_settings()
    scene=None;cameras=None;pipeline=None;body=None;frames=[];failed=True;restored=False
    cleanup_errors=[]
    try:
        settings=world.get_settings()
        settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        scene=spawn_native_scene(world,carla,geometry_path,config["case_branch"],config["vehicle_blueprint_id"])
        cameras=NativeCameraFrameJoin(root,world,carla,scene)
        pipeline=PipelineCapture(client,scene["ego"],root,config["selected_case_id"],
                                 required_observations=config.get("required_atoms",[]))
        body=OriginalCurbBodyCapture(root,world,scene,geometry_path,pipeline)
        waypoint=0;start=None
        for _ in range(config["frames"]):
            control=apply_route_control(scene,carla,waypoint,config.get("target_speed_mps",4.0))
            if control["reached"] and waypoint<len(route["route_xy_m"])-1:waypoint+=1
            frame=world.tick();snapshot=world.get_snapshot()
            if snapshot.frame!=frame:raise ValueError("Native curb tick/snapshot differs")
            if start is None:start=snapshot.timestamp.elapsed_seconds
            time_s=snapshot.timestamp.elapsed_seconds-start
            body.capture(frame,time_s,cameras)
            frames.append(frame)
        cameras.verify_frames(frames)
        failed=False
    finally:
        for action in ((lambda:body.close()) if body is not None else None,
                       (lambda:pipeline.close(confirmed=not failed)) if pipeline is not None else None,
                       (lambda:cameras.close()) if cameras is not None else None):
            if action is not None:
                try:action()
                except BaseException as error:cleanup_errors.append(str(error))
        if scene is not None:
            for actor in reversed(scene["actors"]):
                try:actor.destroy()
                except BaseException as error:cleanup_errors.append(str(error))
        try:
            world.apply_settings(original)
            current=world.get_settings()
            restored=(current.synchronous_mode==original.synchronous_mode and
                      current.fixed_delta_seconds==original.fixed_delta_seconds)
        except BaseException as error:cleanup_errors.append(str(error))
        if not restored:raise ValueError("Native curb world settings restoration differs")
    if cleanup_errors or failed or len(frames)!=config["frames"]:
        raise ValueError("Native curb capture did not finish")
    (root/"acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind":"native","diagnostic_fixture":False,
        "original_frames":len(frames)},indent=2)+"\n")
    seal_curb_sources(root,config["selected_case_id"])
    seal_capture(root,frames=len(frames),restoration={"restored":restored},
                 errors=[],encoder_exit_codes={name:0 for name in CAMERAS},
                 context={"native_map_name":world.get_map().name,
                          "source_geometry_sha256":route["geometry_sha256"]})
    return {"case_id":config["selected_case_id"],"frames":len(frames),
            "source_geometry_sha256":route["geometry_sha256"],
            "physical_acceptance_claimed":False,"legal_acceptance_claimed":False}

CAMERAS=("overview","approach","reference_corner","driver_reference")

def finalize_original_sources(attempt):
    """Derive measured curb streams only from a sealed original-source bundle."""
    root=Path(attempt)
    receipt=_load(root/"curb_source_receipt.json")
    required={"oneway_geometry_original.json","body_ground_original.json",
              "trace.jsonl","video_frames.jsonl"}
    required|={name+".mkv" for name in CAMERAS}
    required|={name+"-frames.jsonl" for name in CAMERAS}
    hashes=receipt.get("source_sha256")
    if not isinstance(hashes,dict) or set(hashes)!=required:
        raise ValueError("original four-camera curb source inventory incomplete")
    for name,expected in hashes.items():
        source=root/name
        if not source.is_file():raise ValueError("Missing required source: "+name)
        if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            raise ValueError("Original curb source SHA-256 mismatch: "+name)
    geometry_path=root/"oneway_geometry_original.json"
    body_path=root/"body_ground_original.json"
    case_id=receipt.get("case_id")
    if not isinstance(case_id,str) or "__" not in case_id:
        raise ValueError("exact one-way turn case identity missing")
    native_route_plan(geometry_path,case_id.split("__")[-1])
    observed=measure(geometry_path,body_path)
    geometry=_load(geometry_path)
    body=_load(body_path)["frames"]
    def lines(name):
        return [json.loads(line) for line in (root/name).read_text().splitlines() if line.strip()]
    trace=lines("trace.jsonl")
    mapping=lines("video_frames.jsonl")
    camera_rows={name:lines(name+"-frames.jsonl") for name in CAMERAS}
    if not body or any(len(rows)!=len(body) for rows in [trace,mapping,*camera_rows.values()]):
        raise ValueError("original curb body/trace/four-camera frame count differs")
    curbs={"approach":_line(geometry["source_left_curb"]),
           "departure":_line(geometry["destination_left_curb"])}
    names=("approach_left_curb_nearest_m","departure_left_curb_nearest_m",
           "original_turn_phase","original_one_way_context","original_left_curb_geometry")
    streams={name:[] for name in names}
    first_time=body[0].get("time_s")
    if type(first_time) not in (int,float) or not isfinite(first_time):
        raise ValueError("original curb start time missing")
    for index,row in enumerate(body):
        frame,time_s=row.get("frame"),row.get("time_s")
        if (type(frame) is not int or type(time_s) not in (int,float) or not isfinite(time_s)
                or abs(time_s-first_time-index*.05)>.005
                or trace[index].get("frame")!=frame
                or mapping[index].get("native_frame")!=frame
                or mapping[index].get("video_frame")!=index
                or abs(trace[index].get("time_s",-1)-time_s)>.005
                or abs(mapping[index].get("time_s",-1)-time_s)>.005):
            raise ValueError("original curb body/trace/frame join differs")
        for name,rows in camera_rows.items():
            if rows[index].get("native_frame")!=frame or abs(rows[index].get("time_s",-1)-time_s)>.005:
                raise ValueError("original curb camera frame join differs: "+name)
        corners=row["ground_corners"]
        if (not isinstance(corners,list) or len(corners)!=4 or
                any(not isinstance(p,list) or len(p)!=2 or
                    any(type(v) not in (int,float) or not isfinite(v) for v in p)
                    for p in corners)):
            raise ValueError("original four-corner footprint missing")
        values={"approach_left_curb_nearest_m":min(abs(_signed(p,curbs["approach"])) for p in corners),
                "departure_left_curb_nearest_m":min(abs(_signed(p,curbs["departure"])) for p in corners),
                "original_turn_phase":row["phase"],
                "original_one_way_context":{"source":"one_way","destination":"one_way","intersection_id":geometry["intersection_id"]},
                "original_left_curb_geometry":{"source":geometry["source_left_curb"],"destination":geometry["destination_left_curb"]}}
        for name,value in values.items():
            streams[name].append({"frame":frame,"time_s":time_s,"phase":row["phase"],"value":value})
    for name,rows in streams.items():
        output=root/(name+".jsonl")
        if output.exists():raise ValueError("derived curb stream already exists: "+name)
        output.write_text("".join(json.dumps(row,allow_nan=False)+"\n" for row in rows))
    return {"case_id":receipt.get("case_id"),"source_sha256":hashes,
            "measurement":observed,
            "measurements":{name:{"method":"finalize_original_sources",
                                  "value":rows,"sources":hashes}
                            for name,rows in streams.items()},
            "recording_evidence":
            [{"name":name,"reference":name+".jsonl","sha256":hashlib.sha256((root/(name+".jsonl")).read_bytes()).hexdigest()}
             for name in names],
            "actual_native_capture":False,"physical_acceptance_claimed":False,"legal_acceptance_claimed":False}

def native_result(attempt, report):
    """Build the pinned Native shape from verified source streams and case config."""
    root=Path(attempt)
    config=_load(root/"config.json")
    description=config.get("case",{}).get("recording_description")
    if not isinstance(description,dict) or report["case_id"]!=config.get("selected_case_id"):
        raise ValueError("exact curb case identity or recording description missing")
    expected_geometry=config.get("source_geometry_sha256")
    if expected_geometry is not None and expected_geometry!=report["source_sha256"]["oneway_geometry_original.json"]:
        raise ValueError("finalized original curb geometry differs from selected config")
    names={"approach_left_curb_nearest_m","departure_left_curb_nearest_m",
           "original_turn_phase","original_one_way_context","original_left_curb_geometry"}
    channels=description.get("channels")
    if not isinstance(channels,list) or {c.get("name") for c in channels if isinstance(c,dict)}!=names or len(channels)!=len(names):
        raise ValueError("exact curb recording channels missing")
    units={c["name"]:c.get("unit") for c in channels}
    if any(not isinstance(v,str) or not v for v in units.values()):
        raise ValueError("curb channel unit missing")
    evidence=[];realized={}
    for name in names:
        item=next((e for e in report["recording_evidence"] if e["name"]==name),None)
        if item is None:raise ValueError("curb derived stream missing: "+name)
        path=root/item["reference"]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item["sha256"]:
            raise ValueError("curb derived stream changed: "+name)
        rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if not rows:raise ValueError("empty curb stream: "+name)
        evidence.append(dict(item,unit=units[name]))
        value=min(row["value"] for row in rows if row["phase"]==("approach" if name.startswith("approach_") else "leaving_intersection")) if name.endswith("_m") else len(rows)
        realized[name]={"value":value,"unit":units[name],
                        "statistic":"phase minimum" if name.endswith("_m") else "sample count",
                        "method":"source-hashed original body/map/frame join",
                        "time_window":"selected original turn interval",
                        "reference":path.name}
    observed=report["measurement"]
    result={"case_id":report["case_id"],
            "measured_values":{"approach_left_curb_nearest_m":observed["approach_left_curb_nearest_m"],
                               "departure_left_curb_nearest_m":observed["departure_left_curb_nearest_m"]},
            "target_checks":[{"target":"source and destination left-curb engineering offsets",
                              "requested":config.get("curb_offsets_m"),
                              "measured":{"approach_m":observed["approach_left_curb_nearest_m"],
                                          "departure_m":observed["departure_left_curb_nearest_m"]},
                              "method":"original source map and body-ground corner join",
                              "tolerance":None,"matched":False,"physical_cause_confirmed":False,
                              "cause_evidence":"Physical realization and legal practicability require independent review"}],
            "setup_confirmed":False,"behavior_attempted":False,"maneuver_completed":False,
            "termination_reason":"Original curb geometry measured; physical outcome unverified",
            "physical_failure_flags":{"independent_visibility_pending":True},
            "trace_reference":"trace.jsonl",
            "video_references":[name+".mkv" for name in CAMERAS],
            "video_frame_map_reference":"video_frames.jsonl",
            "recording_description":description,"recording_evidence":evidence,
            "realized_observables":realized,"physical_acceptance_claimed":False,
            "legal_acceptance_claimed":False}
    from worker_exchange.native_output import validate_result
    return validate_result(result)

def finalize_and_write(attempt, output):
    """Run source conversion and write one Native result for a fresh attempt."""
    root=Path(attempt)
    destination=Path(output)
    if destination.exists() or (root/"result.json").exists():
        raise ValueError("retain prior curb analysis; choose a fresh attempt")
    _load(root/"config.json")
    report=finalize_original_sources(root)
    result=native_result(root,report)
    from worker_exchange.native_output import write_result
    write_result(root,result)
    destination.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    return result

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--geometry");ap.add_argument("--body");ap.add_argument("--attempt")
    ap.add_argument("--output");ap.add_argument("--run-native",action="store_true")
    ap.add_argument("--output-dir")
    ap.add_argument("--check",action="store_true")
    ap.add_argument("--host",default="127.0.0.1");ap.add_argument("--port",type=int,default=2000)
    a=ap.parse_args()
    if a.run_native or a.check or a.output_dir:
        if a.body or a.output:ap.error("Native capture/check cannot mix body/output")
        root=Path(a.attempt or a.output_dir or ".")
        geometry=Path(a.geometry) if a.geometry else root/"source_geometry.json"
        if a.check:check_native_config(_load(root/"config.json"),geometry)
        else:run_native(root,geometry,a.host,a.port)
    elif a.attempt:
        if a.geometry or a.body:ap.error("--attempt cannot be mixed with geometry/body")
        if not a.output:ap.error("--output required for finalization")
        finalize_and_write(a.attempt,a.output)
    elif a.geometry and a.body:
        if not a.output:ap.error("--output required for measurement")
        Path(a.output).write_text(json.dumps(measure(a.geometry,a.body),indent=2)+"\n")
    else:ap.error("supply --attempt or both --geometry and --body")
"""Independent fixed-condition comparison for both left-curb clauses."""
import json
from pathlib import Path

def audit(paths,variable):
    if variable not in ("approach_curb_position","turn_departure_curb_position") or len(paths)!=2:
        raise ValueError("two exact cases and known comparison variable required")
    a,b=[json.loads(Path(p).read_text()) for p in paths]
    for r in (a,b):
        if len(r.get("source_refs",[]))!=2 or r.get("legal_conclusion") is not None:
            raise ValueError("source-bound original measurement missing or legal conclusion asserted")
        hashes=r.get("source_sha256",{})
        for source in r["source_refs"]:
            p=Path(source)
            if not p.is_file() or hashes.get(source)!=hashlib.sha256(p.read_bytes()).hexdigest():
                raise ValueError("missing or changed original source: "+source)
    for key in ("subject_id","intersection_id","source_directionality","destination_directionality","maneuver"):
        if a.get(key)!=b.get(key):raise ValueError("fixed geometry or identity changed: "+key)
    if variable=="approach_curb_position":
        fixed,varied="departure_left_curb_nearest_m","approach_left_curb_nearest_m"
    else:
        fixed,varied="approach_left_curb_nearest_m","departure_left_curb_nearest_m"
    if abs(a[fixed]-b[fixed])>.001:raise ValueError("held curb position changed: "+fixed)
    if abs(a[varied]-b[varied])<.001:raise ValueError("deliberate measured curb position did not vary")
    return {"comparison_complete":True,"variable":variable,"fixed_conditions_checked":["subject_id","intersection_id","one-way directionalities",fixed],"legal_conclusion":None}

if __name__=="__main__":main()
