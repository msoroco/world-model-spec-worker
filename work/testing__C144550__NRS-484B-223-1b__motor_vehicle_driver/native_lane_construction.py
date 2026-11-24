"""Select a real adjacent Native driving lane and its marked boundary."""

import json
import math
import subprocess
import sys
from contextlib import contextmanager
from queue import Empty,Queue

from shapely.geometry import MultiPoint,Polygon

CASE_PREFIX="testing__C144550__NRS-484B-223-1b__motor_vehicle_driver__"
SIGNAL_CASES={
    "left_signal_before_clear_gap":("left","before"),
    "left_signal_late_clear_gap":("left","late"),
    "left_wrong_signal_clear_gap":("left","wrong"),
    "left_signal_before_close_gap":("left","before"),
    "right_signal_before_clear_gap":("right","before"),
}
CAMERA_SIZES={"overview":(1920,1080),"approach":(1280,720),
              "reference_corner":(1280,720),"driver_reference":(1280,720)}


def camera_transforms_for_site(carla, site, overview_along_m=65):
    """Construct candidate camera poses from the selected Native lane spawn.

    These are acquisition poses; original pixels must still establish that the
    marking, complete vehicles and indicators are visible before acceptance.
    """
    spawn=site.get("spawn") if isinstance(site,dict) else None
    if spawn is None or not hasattr(spawn,"location") or not hasattr(spawn,"rotation"):
        raise ValueError("Selected Native lane spawn required for cameras")
    loc=spawn.location
    yaw=float(spawn.rotation.yaw)
    values=(float(loc.x),float(loc.y),float(loc.z),yaw)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Finite selected Native site pose required")
    if (type(overview_along_m) not in (int,float) or not math.isfinite(overview_along_m)
            or not 30<=overview_along_m<=100):
        raise ValueError("Bounded Native overview position required")
    rad=math.radians(yaw)
    fx,fy=math.cos(rad),math.sin(rad)
    lx,ly=-fy,fx
    def static(along,side,height,yaw_delta,pitch):
        return carla.Transform(
            carla.Location(x=loc.x+along*fx+side*lx,
                           y=loc.y+along*fy+side*ly,z=loc.z+height),
            carla.Rotation(yaw=yaw+yaw_delta,pitch=pitch))
    return {
        "overview":static(overview_along_m,0,48,0,-82),
        "approach":static(-24,12,9,-15,-12),
        "reference_corner":static(50,-18,14,145,-25),
        "driver_reference":carla.Transform(
            carla.Location(x=0.8,y=0,z=1.6),
            carla.Rotation(yaw=0,pitch=-5)),
    }


@contextmanager
def source_cameras(world,ego,transforms,timeout_s=10):
    """Acquire four original Native RGB streams at the pinned camera profile.

    Static overview/detail transforms are site-specific inputs; only the driver
    view attaches to ego. Pixel coverage is judged after Native capture.
    """
    if set(transforms)!=set(CAMERA_SIZES) or not isinstance(timeout_s,(int,float)) or timeout_s<=0:
        raise ValueError("Four site-specific camera transforms and positive timeout required")
    sensors={};queues={name:Queue() for name in CAMERA_SIZES}
    try:
        for name,(width,height) in CAMERA_SIZES.items():
            blueprint=world.get_blueprint_library().find("sensor.camera.rgb")
            for key,value in (("image_size_x",width),("image_size_y",height),
                              ("fov",90),("sensor_tick",.05)):
                blueprint.set_attribute(key,str(value))
            kwargs={"attach_to":ego} if name=="driver_reference" else {}
            sensor=world.spawn_actor(blueprint,transforms[name],**kwargs)
            if sensor is None:raise ValueError("Native camera spawn failed: "+name)
            sensors[name]=sensor
            sensor.listen(lambda image,name=name:queues[name].put(image))
        def source(name):
            def read(expected):
                for _ in range(8):
                    try:image=queues[name].get(timeout=timeout_s)
                    except Empty as error:
                        raise ValueError("Missing original Native camera frame: "+name) from error
                    if image.frame==expected:return image
                    if image.frame>expected:
                        raise ValueError("Native camera skipped expected frame: "+name)
                raise ValueError("Native camera frame backlog exceeded: "+name)
            return read
        yield {name:source(name) for name in CAMERA_SIZES}
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop();sensor.destroy()


class FFV1CameraWriter:
    """Retain one original Native BGRA camera as a lossless FFV1 source."""
    def __init__(self,path,width,height,expected_frames=900):
        from pathlib import Path
        path=Path(path)
        if path.exists() or not path.parent.is_dir():
            raise ValueError("Fresh camera source path in existing attempt required")
        if any(type(value) is not int or value<=0 for value in (width,height,expected_frames)):
            raise ValueError("Positive camera dimensions and frame count required")
        self.path,self.width,self.height,self.expected_frames=path,width,height,expected_frames
        self.frames=0;self.exit_code=None
        self.process=subprocess.Popen([
            "ffmpeg","-hide_banner","-loglevel","error","-n",
            "-f","rawvideo","-pixel_format","bgra",
            "-video_size",f"{width}x{height}","-framerate","20",
            "-i","pipe:0","-an","-c:v","ffv1","-level","3",
            "-pix_fmt","bgr0",str(path)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)

    def write(self,image):
        if (getattr(image,"width",None),getattr(image,"height",None))!=(self.width,self.height):
            raise ValueError("Original Native camera dimensions differ")
        data=bytes(image.raw_data)
        if len(data)!=self.width*self.height*4:
            raise ValueError("Incomplete original Native BGRA camera frame")
        if self.process.poll() is not None:
            raise ValueError("Source camera encoder exited during capture")
        self.process.stdin.write(data)
        self.frames+=1

    def close(self):
        if self.exit_code is not None:return self.exit_code
        if not self.process.stdin.closed:self.process.stdin.close()
        try:code=self.process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            self.process.kill();self.process.wait()
            code=self.process.returncode
        error=self.process.stderr.read().decode(errors="replace")
        self.process.stderr.close();self.exit_code=code
        if code!=0 or (self.frames and not self.path.is_file()):
            raise ValueError("FFV1 source camera encoder failed: "+error[-1000:])
        return code

    def require_complete(self):
        if self.exit_code!=0 or self.frames!=self.expected_frames or not self.path.is_file():
            raise ValueError("Incomplete original FFV1 camera source")
        return {"path":str(self.path),"frames":self.frames,
                "width":self.width,"height":self.height,"fps":20,"encoding":"ffv1-bgr0"}


def select_adjacent_marked_lane(waypoint, direction, lane_type_driving):
    if direction not in ("left","right"):
        raise ValueError("Lane-change direction must be left or right")
    neighbor=waypoint.get_left_lane() if direction=="left" else waypoint.get_right_lane()
    if neighbor is None or neighbor.lane_type!=lane_type_driving:
        raise ValueError("No adjacent Native driving lane in requested direction")
    if neighbor.road_id!=waypoint.road_id or neighbor.lane_id==waypoint.lane_id:
        raise ValueError("Adjacent lane road/identity mismatch")
    if waypoint.lane_id==0 or neighbor.lane_id==0 or (waypoint.lane_id>0)!=(neighbor.lane_id>0):
        raise ValueError("Adjacent lane travels in the opposite direction")
    marking=waypoint.left_lane_marking if direction=="left" else waypoint.right_lane_marking
    if marking is None or str(marking.type).lower().endswith("none"):
        raise ValueError("No visible Native lane marking at crossing boundary")
    return {"source":waypoint,"target":neighbor,"marking":marking,
            "direction":direction,"source_lane_id":waypoint.lane_id,
            "target_lane_id":neighbor.lane_id}


def _body_xy(actor):
    vertices=actor.bounding_box.get_world_vertices(actor.get_transform())
    points=[[float(vertex.x),float(vertex.y)] for vertex in vertices]
    if len(points)<4 or any(not all(math.isfinite(value) for value in point) for point in points):
        raise ValueError("Incomplete original Native body vertices")
    if MultiPoint(points).convex_hull.area<=0:
        raise ValueError("Degenerate original Native body")
    return points


def sample_source_lane_polygon(source,forward_m=260,backward_m=10,step_m=2):
    """Retain Native lane edges along the whole planned motion corridor."""
    if any(type(value) not in (int,float) or not math.isfinite(value) or value<=0
           for value in (forward_m,backward_m,step_m)):
        raise ValueError("Finite positive Native lane sampling distances required")
    def advance(waypoint,method):
        options=[next_waypoint for next_waypoint in getattr(waypoint,method)(step_m)
                 if next_waypoint.road_id==source.road_id and next_waypoint.lane_id==source.lane_id]
        if len(options)!=1:raise ValueError("Native source lane corridor is interrupted or branches")
        return options[0]
    before=[];waypoint=source
    for _ in range(math.ceil(backward_m/step_m)):
        waypoint=advance(waypoint,"previous");before.append(waypoint)
    after=[];waypoint=source
    for _ in range(math.ceil(forward_m/step_m)):
        waypoint=advance(waypoint,"next");after.append(waypoint)
    centerline=list(reversed(before))+[source]+after
    left=[];right=[]
    for waypoint in centerline:
        location=waypoint.transform.location
        yaw=math.radians(float(waypoint.transform.rotation.yaw))
        width=float(waypoint.lane_width)
        if not all(math.isfinite(value) for value in (location.x,location.y,yaw,width)) or width<=1:
            raise ValueError("Finite Native source lane width and pose required")
        nx,ny=-math.sin(yaw),math.cos(yaw)
        left.append([float(location.x+nx*width/2),float(location.y+ny*width/2)])
        right.append([float(location.x-nx*width/2),float(location.y-ny*width/2)])
    polygon=left+list(reversed(right))
    geometry=Polygon(polygon)
    if not geometry.is_valid or geometry.area<=0:
        raise ValueError("Sampled Native source lane polygon is invalid")
    return polygon


def find_native_lane_site(world,direction,lane_type_driving,target_lane_id=None):
    """Choose a deterministic marked same-direction corridor from Native map spawns."""
    mapping=world.get_map()
    candidates=[]
    for spawn in mapping.get_spawn_points():
        waypoint=mapping.get_waypoint(spawn.location,project_to_road=False)
        if waypoint is None:continue
        try:
            selected=select_adjacent_marked_lane(waypoint,direction,lane_type_driving)
            if target_lane_id is not None and selected["target_lane_id"]!=target_lane_id:
                continue
            polygon=sample_source_lane_polygon(waypoint)
        except ValueError:
            continue
        location=spawn.location
        if not all(math.isfinite(float(value)) for value in (location.x,location.y,location.z)):
            continue
        key=(int(waypoint.road_id),int(waypoint.lane_id),
             round(float(location.x),3),round(float(location.y),3))
        candidates.append((key,spawn,selected,polygon))
    if not candidates:raise ValueError("No uninterrupted marked same-direction Native lane corridor")
    _,spawn,selected,polygon=min(candidates,key=lambda item:item[0])
    return {"spawn":spawn,"selected":selected,"source_polygon":polygon,
            "candidate_count":len(candidates),"selection_rule":"lowest road/lane/spawn coordinates"}


@contextmanager
def stage_native_lane_case(world,site,case_id,vehicle_blueprint,
                           requested_distance_m=None):
    """Spawn source-lane ego and a measurable target-lane actor; release both."""
    if not isinstance(site,dict) or not all(key in site for key in ("spawn","selected")):
        raise ValueError("Verified Native lane site required")
    selected=site["selected"]
    suffix=case_id[len(CASE_PREFIX):] if case_id.startswith(CASE_PREFIX) else ""
    if suffix not in SIGNAL_CASES or SIGNAL_CASES[suffix][0]!=selected.get("direction"):
        raise ValueError("Exact case and selected lane direction differ")
    target=selected.get("target")
    if target is None:raise ValueError("Selected Native target lane required")
    # Distances are scenario construction knobs, never statutory gap thresholds.
    requested_distance=(25 if suffix.endswith("close_gap") else 245) if requested_distance_m is None else requested_distance_m
    if (type(requested_distance) not in (int,float) or not math.isfinite(requested_distance)
            or not 10<=requested_distance<=250):
        raise ValueError("Bounded target-lane staging distance required")
    candidates=[waypoint for waypoint in target.next(requested_distance)
                if waypoint.road_id==target.road_id and waypoint.lane_id==target.lane_id]
    if len(candidates)!=1:raise ValueError("Target-lane staging corridor interrupted or branches")
    staged=[]
    try:
        for role,transform in (("ego",site["spawn"]),("target",candidates[0].transform)):
            actor=world.try_spawn_actor(vehicle_blueprint,transform)
            if actor is None:raise ValueError("Native vehicle spawn failed: "+role)
            staged.append(actor)
            actor.set_autopilot(False)
        yield {"ego":staged[0],"target":staged[1],
               "target_initial_route_distance_m":requested_distance,
               "target_behavior":"stationary at staged Native waypoint; measure actual body gap"}
    finally:
        for actor in reversed(staged):actor.destroy()


def make_native_lane_context(world,selected,source_polygon):
    """Bind the two observed marked same-direction lanes to the sampled map."""
    if not isinstance(selected,dict) or not all(selected.get(key) is not None for key in
                                              ("source","target","marking","direction")):
        raise ValueError("Verified Native adjacent marked lanes required")
    if not Polygon(source_polygon).is_valid or Polygon(source_polygon).area<=0:
        raise ValueError("Valid sampled Native source polygon required")
    source,target=selected["source"],selected["target"]
    if source.road_id!=target.road_id or source.lane_id==target.lane_id or source.lane_id*target.lane_id<=0:
        raise ValueError("Native source and target are not same-direction lanes")
    def lane_row(waypoint):
        yaw=math.radians(float(waypoint.transform.rotation.yaw))
        return {"road_id":waypoint.road_id,"lane_id":waypoint.lane_id,
                "forward_xy":[math.cos(yaw),math.sin(yaw)],
                "marking_source":"Native adjacent boundary "+str(selected["marking"].type)}
    return {"native_map_id":world.get_map().name,"road_id":source.road_id,
            "source_lane_id":source.lane_id,"target_lane_id":target.lane_id,
            "marked_lane_source":"Native adjacent boundary "+str(selected["marking"].type),
            "same_direction_lane_count_source":"two observed adjacent Native driving-lane waypoints",
            "lane_boundary_source":"sampled Native source waypoint centers, headings and lane widths",
            "target_traffic_source":"original Native target-lane actor bodies",
            "signal_display_source":"Native turn-lamp readback; original detail camera required for display review",
            "same_direction_marked_lane_count":2,"change_direction":selected["direction"],
            "same_direction_lanes":[lane_row(source),lane_row(target)],
            "source_lane_polygon_xy_m":source_polygon,
            "lane_forward_xy":lane_row(source)["forward_xy"]}


def make_original_observer(world,ego,selected,light_states,source_polygon):
    """Read original Native body, lane, lamp and target traffic on each tick."""
    lane=Polygon(source_polygon)
    if not lane.is_valid or lane.area<=0:raise ValueError("Valid source lane polygon required")
    road_id=selected["source"].road_id;target_lane_id=selected["target_lane_id"]
    def observe(frame,time_s):
        transform=ego.get_transform()
        waypoint=world.get_map().get_waypoint(transform.location,project_to_road=False)
        if waypoint is None or waypoint.road_id!=road_id:
            raise ValueError("Original ego Native road readback differs")
        body=_body_xy(ego)
        lights=int(ego.get_light_state())
        left=bool(lights&int(light_states.LeftBlinker))
        right=bool(lights&int(light_states.RightBlinker))
        if left and right:raise ValueError("Ambiguous original Native indicator readback")
        indicator="left" if left else ("right" if right else "off")
        others=[]
        for actor in world.get_actors().filter("vehicle.*"):
            if actor.id==ego.id:continue
            other_waypoint=world.get_map().get_waypoint(actor.get_transform().location,
                                                         project_to_road=False)
            if other_waypoint is None or other_waypoint.road_id!=road_id or other_waypoint.lane_id!=target_lane_id:
                continue
            others.append({"actor_id":int(actor.id),"road_id":road_id,"lane_id":target_lane_id,
                           "body_vertices_xy_m":_body_xy(actor)})
        others.sort(key=lambda row:row["actor_id"])
        return {"frame":frame,"time_s":time_s,"road_id":road_id,
                "ego_lane_id":waypoint.lane_id,"ego_body_vertices_xy_m":body,
                "indicator":indicator,"target_lane_bodies":others,
                "body_left_source_lane":not lane.covers(MultiPoint(body).convex_hull)}
    return observe


def indicator_command(case_id, body_left_source_lane):
    """Choose the planned signal; original frames still decide what displayed."""
    if type(body_left_source_lane) is not bool:
        raise ValueError("Original body-departure observation required")
    if not case_id.startswith(CASE_PREFIX) or case_id[len(CASE_PREFIX):] not in SIGNAL_CASES:
        raise ValueError("Unknown exact lane-change case")
    direction,policy=SIGNAL_CASES[case_id[len(CASE_PREFIX):]]
    if policy=="late" and not body_left_source_lane:return "off"
    if policy=="wrong":return "right" if direction=="left" else "left"
    return direction


def apply_indicator(ego, light_states, command):
    """Set turn lamps without clearing unrelated Native vehicle lights."""
    if command not in ("off","left","right"):
        raise ValueError("Invalid indicator command")
    left=int(light_states.LeftBlinker)
    right=int(light_states.RightBlinker)
    current=int(ego.get_light_state())
    state=current & ~(left|right)
    if command=="left":state|=left
    if command=="right":state|=right
    ego.set_light_state(light_states(state))
    return {"requested_indicator":command,"readback_state":int(ego.get_light_state())}


def route_target_for_tick(world,ego,selected,lookahead_m=8):
    """Resolve a forward waypoint in the selected target lane at the current pose."""
    if not isinstance(lookahead_m,(int,float)) or isinstance(lookahead_m,bool) or not 2<=lookahead_m<=30:
        raise ValueError("Bounded Native route lookahead required")
    current=world.get_map().get_waypoint(ego.get_transform().location,project_to_road=False)
    if current is None or current.road_id!=selected["source"].road_id:
        raise ValueError("Native ego left selected source road")
    if current.lane_id==selected["target_lane_id"]:
        lane=current
    elif current.lane_id==selected["source_lane_id"]:
        lane=current.get_left_lane() if selected["direction"]=="left" else current.get_right_lane()
    else:
        raise ValueError("Native ego entered an unselected lane")
    if lane is None or lane.road_id!=current.road_id or lane.lane_id!=selected["target_lane_id"]:
        raise ValueError("Selected target lane disappeared at current Native pose")
    candidates=[waypoint for waypoint in lane.next(lookahead_m)
                if waypoint.road_id==lane.road_id and waypoint.lane_id==lane.lane_id]
    if len(candidates)!=1:raise ValueError("Native target-lane route interrupted or branches")
    return candidates[0]


def step_toward_marked_lane(ego, selected, case_id, body_left_source_lane,
                            light_states, control_factory, target_speed_mps=5.0,
                            target_waypoint=None):
    """Issue one bounded Native control step toward the verified adjacent lane.

    The target is a route waypoint, not a claimed safe gap or legal decision.
    The caller must retain the original actor, marking and lamp observations.
    """
    if selected.get("direction") not in ("left", "right") or selected.get("target") is None:
        raise ValueError("Verified adjacent lane selection required")
    if not isinstance(target_speed_mps, (int, float)) or isinstance(target_speed_mps, bool):
        raise ValueError("Finite target speed required")
    if not math.isfinite(target_speed_mps) or not 0 < target_speed_mps <= 15:
        raise ValueError("Bounded target speed required")
    suffix=case_id[len(CASE_PREFIX):] if case_id.startswith(CASE_PREFIX) else ""
    if suffix not in SIGNAL_CASES or SIGNAL_CASES[suffix][0]!=selected["direction"]:
        raise ValueError("Exact case and selected lane direction differ")
    target=(target_waypoint or selected["target"]).transform.location
    transform=ego.get_transform()
    here=transform.location
    dx,dy=target.x-here.x,target.y-here.y
    if not all(math.isfinite(v) for v in (dx,dy,transform.rotation.yaw)) or math.hypot(dx,dy)<0.25:
        raise ValueError("Distinct finite Native route target required")
    desired=math.atan2(dy,dx)
    yaw=math.radians(transform.rotation.yaw)
    error=math.atan2(math.sin(desired-yaw),math.cos(desired-yaw))
    steer=max(-0.7,min(0.7,error/1.2))
    velocity=ego.get_velocity()
    speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    if not math.isfinite(speed):
        raise ValueError("Finite Native speed required")
    throttle=0.25 if speed<target_speed_mps else 0.0
    brake=0.2 if speed>target_speed_mps+2 else 0.0
    signal=apply_indicator(ego,light_states,indicator_command(case_id,body_left_source_lane))
    control=control_factory(throttle=throttle,steer=steer,brake=brake,
                            reverse=False,manual_gear_shift=False)
    ego.apply_control(control)
    return {"control":control,"signal":signal,"target_lane_id":selected.get("target_lane_id"),
            "heading_error_rad":error,"observed_speed_mps":speed,
            "legal_safety_ascertainment":"unresolved"}


def capture_native_case(world, ego, selected, case_id, light_states, control_factory,
                        observe_original, camera_sources, camera_writers,
                        frame_map, lane_history_stream, capture_pipeline_frame,
                        frames=900, target_speed_mps=5.0):
    """Tick one exact Native case with joined source rows and four raw cameras.

    The caller supplies a native_output.FrameMap and an exclusive lane-history
    stream and the pinned PipelineCapture.capture callback. Identities and
    observations are written during acquisition, after all four cameras and
    the shared graph/trace capture join the current Native frame. The caller
    owns PipelineCapture closure and final sealing.
    """
    names=("overview","approach","reference_corner","driver_reference")
    if type(frames) is not int or frames!=900:
        raise ValueError("Exact 45-second capture requires 900 frames")
    if set(camera_sources)!=set(names) or set(camera_writers)!=set(names):
        raise ValueError("Four named original camera streams required")
    if any(not all(callable(getattr(camera_writers[name],method,None))
                   for method in ("write","close","require_complete")) for name in names):
        raise ValueError("Four sealable original camera writers required")
    if not callable(getattr(frame_map,"append",None)) or not callable(getattr(frame_map,"close",None)):
        raise ValueError("Capture-time native_output.FrameMap required")
    if not callable(getattr(lane_history_stream,"write",None)) or not callable(getattr(lane_history_stream,"close",None)):
        raise ValueError("Exclusive original lane-history stream required")
    if not callable(capture_pipeline_frame):
        raise ValueError("Pinned shared graph/trace capture callback required")
    rows=[];last_frame=-1;last_time=-math.inf;left_source=False
    try:
        for _ in range(frames):
            target_waypoint=route_target_for_tick(world,ego,selected)
            command=step_toward_marked_lane(
                ego,selected,case_id,left_source,light_states,control_factory,
                target_speed_mps=target_speed_mps,target_waypoint=target_waypoint)
            frame=world.tick()
            snapshot=world.get_snapshot()
            time=float(snapshot.timestamp.elapsed_seconds)
            if type(frame) is not int or frame<=last_frame or not math.isfinite(time) or time<=last_time:
                raise ValueError("Nonmonotone Native frame or time")
            last_frame,last_time=frame,time
            row=observe_original(frame,time)
            if not isinstance(row,dict) or row.get("frame")!=frame or row.get("time_s")!=time:
                raise ValueError("Original lane observation frame join failed")
            left_source=row.get("body_left_source_lane")
            if type(left_source) is not bool:
                raise ValueError("Original body-departure observation required")
            row=dict(row)
            row["requested_indicator"]=command["signal"]["requested_indicator"]
            row["native_light_readback"]=command["signal"]["readback_state"]
            for name in names:
                image=camera_sources[name](frame)
                if getattr(image,"frame",None)!=frame:
                    raise ValueError("Camera skipped Native frame: "+name)
                camera_writers[name].write(image)
            capture_pipeline_frame(frame,time)
            frame_map.append(frame,time)
            lane_history_stream.write(json.dumps(row,sort_keys=True,allow_nan=False)+"\n")
            rows.append(row)
    finally:
        failed=sys.exc_info()[0] is not None
        close_errors=[]
        for resource in [*(camera_writers[name] for name in names),frame_map,lane_history_stream]:
            try:resource.close()
            except Exception as error:close_errors.append(str(error))
        if close_errors and not failed:
            raise ValueError("Native capture source closure failed: "+"; ".join(close_errors))
    for name in names:
        camera_writers[name].require_complete()
    return rows
