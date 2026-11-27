"""Lazy CARLA acquisition for original NRS 484B.270(3) encounters.

The CPU fixture tests this module's geometry and policy, not CARLA motion.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from cycle_lane_2703 import VIEWS, intersects, _polygon


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def control(position, yaw_rad, speed, route, target_speed=4.0, hold=False, park=False):
    """Route-following target, with deliberate yield/standing holds."""
    if hold or park:
        return {"throttle": 0.0, "steer": 0.0, "brake": 1.0,
                "hand_brake": bool(park), "route_complete": False}
    points = [tuple(p) for p in route]
    if len(points) < 2 or any(len(p) != 2 for p in points):
        raise ValueError("two-point controlled route required")
    x, y = position
    if any(not math.isfinite(v) for v in (x, y, yaw_rad, speed, target_speed)):
        raise ValueError("finite controlled motion required")
    nearest = min(range(len(points)), key=lambda i: math.dist((x, y), points[i]))
    lookahead = max(2.0, min(6.0, 2.0 + speed * 0.5))
    target = points[-1]
    for point in points[nearest + 1:]:
        if math.dist((x, y), point) >= lookahead:
            target = point
            break
    heading = math.atan2(target[1] - y, target[0] - x)
    angle = (heading - yaw_rad + math.pi) % (2 * math.pi) - math.pi
    remaining = math.dist((x, y), points[-1])
    if remaining < 0.7:
        return {"throttle": 0.0, "steer": 0.0, "brake": 1.0,
                "hand_brake": False, "route_complete": True}
    error = target_speed - speed
    return {"throttle": max(0.0, min(0.5, 0.16 * error)),
            "steer": max(-1.0, min(1.0, 1.2 * angle)),
            "brake": max(0.0, min(0.5, -0.12 * error)),
            "hand_brake": False, "route_complete": False}


def body_polygon(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted(set((v.x, v.y) for v in vertices))
    if len(points) < 3:
        raise ValueError("Native actor body polygon degenerate")
    def cross(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower, upper = [], []
    for point in points:
        while len(lower) > 1 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) > 1 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return [list(p) for p in _polygon([list(p) for p in lower[:-1]+upper[:-1]])], vertices


class NativeAdapter:
    def __init__(self, host, port, output, sources, plan):
        import carla
        self.carla = carla
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.sources = sources
        self.plan = plan
        self.site = json.loads(sources["site"].read_text())
        xodr = self.site.get("map_xodr", {})
        root = sources["site"].resolve().parent
        road = (root / xodr.get("path", "")).resolve()
        if (not xodr.get("path") or not road.is_relative_to(root) or
                road.suffix != ".xodr" or not road.is_file() or
                sha(road) != xodr.get("sha256")):
            raise ValueError("reviewed original OpenDRIVE bytes required")
        self.road = road
        self.client = carla.Client(host, port)
        self.client.set_timeout(30.0)
        self.world = self.client.generate_opendrive_world(road.read_text())
        if self.world.get_map().name != plan["map_id"]:
            raise ValueError("Native map identity differs from reviewed site")
        self.old_settings = self.world.get_settings()
        self.owned = []
        self.sensors = {}
        self.recorder_started = False
        self.restoration_verified = False
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)
        self.client.start_recorder(str(self.output / "carla_recorder.log"))
        self.recorder_started = True

    def _spawn(self, blueprint_id, route, height):
        first, second = route[:2]
        yaw = math.degrees(math.atan2(second[1]-first[1],second[0]-first[0]))
        bp = self.world.get_blueprint_library().find(blueprint_id)
        if bp is None:
            raise ValueError("reviewed actor blueprint unavailable: " + blueprint_id)
        pose = self.carla.Transform(self.carla.Location(x=first[0],y=first[1],z=height),
                                    self.carla.Rotation(yaw=yaw))
        actor = self.world.try_spawn_actor(bp, pose)
        if actor is None:
            raise ValueError("source actor spawn failed: " + blueprint_id)
        self.owned.append(actor)
        return actor

    def _cameras(self, ego, cameras):
        poses = {"overview": (-7.0,0.0,3.0,-12.0),
                 "approach": (2.0,0.0,1.7,0.0),
                 "reference_corner": (-3.0,2.5,2.3,-8.0),
                 "driver_reference": (0.1,0.0,1.55,0.0)}
        for camera in cameras:
            name = camera["name"]
            bp = self.world.get_blueprint_library().find("sensor.camera.rgb")
            if bp is None:
                raise ValueError("Native RGB camera unavailable")
            bp.set_attribute("image_size_x",str(camera["width"]))
            bp.set_attribute("image_size_y",str(camera["height"]))
            bp.set_attribute("sensor_tick","0.05")
            x,y,z,pitch = poses[name]
            transform = self.carla.Transform(self.carla.Location(x=x,y=y,z=z),
                                             self.carla.Rotation(pitch=pitch))
            sensor = self.world.spawn_actor(bp,transform,attach_to=ego)
            self.owned.append(sensor)
            pending = queue.Queue(maxsize=4)
            sensor.listen(pending.put)
            self.sensors[name] = pending

    def execute(self, config, participant_source):
        plan = self.plan
        site = self.site
        participant = json.loads(participant_source.read_text())
        height = site.get("spawn_height_m", {})
        if not all(k in height and isinstance(height[k],(int,float)) for k in ("ego","participant")):
            raise ValueError("reviewed original spawn heights required")
        ego_bp = site.get("ego_blueprint_id")
        if not isinstance(ego_bp,str) or not ego_bp.startswith("vehicle."):
            raise ValueError("source motor-vehicle blueprint required")
        ego = self._spawn(ego_bp,plan["ego_route"],height["ego"])
        other = self._spawn(plan["participant_blueprint_id"],plan["participant_route"],height["participant"])
        if plan["participant_kind"] in ("bicycle","electric_bicycle","electric_scooter"):
            rider_blueprint = participant.get("rider_blueprint_id")
            if not isinstance(rider_blueprint,str) or not rider_blueprint.startswith("walker."):
                raise ValueError("separate physical rider blueprint required")
            rider_bp = self.world.get_blueprint_library().find(rider_blueprint)
            rider_pose = self.carla.Transform(self.carla.Location(z=0.7))
            rider = self.world.try_spawn_actor(rider_bp,rider_pose,attach_to=other)
            if rider is None:
                raise ValueError("physical rider spawn failed")
            self.owned.append(rider)
        else:
            rider = None
        self._cameras(ego,config["cameras"])
        facility = _polygon(plan["facility_polygon"])
        conflict = _polygon(plan["conflict_polygon"])
        history = []
        trace_path = self.output/"trace.jsonl"
        map_path = self.output/"video_frames.jsonl"
        evidence_path = self.output/"capture/evidence.jsonl"
        native_path = self.output/"capture/native/frames.jsonl"
        evidence_path.parent.mkdir(parents=True,exist_ok=True)
        native_path.parent.mkdir(parents=True,exist_ok=True)
        other_passed = False
        lane_hold_start = None
        with trace_path.open("x") as trace, map_path.open("x") as frame_map, evidence_path.open("x") as evidence, native_path.open("x") as native_index:
            for index in range(900):
                ego_transform = ego.get_transform()
                ego_location = ego_transform.location
                ego_velocity = ego.get_velocity()
                ego_speed = math.hypot(ego_velocity.x,ego_velocity.y)
                other_transform = other.get_transform()
                other_location = other_transform.location
                other_velocity = other.get_velocity()
                other_speed = math.hypot(other_velocity.x,other_velocity.y)
                ego_body,_ = body_polygon(ego)
                other_body,_ = body_polygon(other)
                if intersects(other_body,conflict):
                    other_passed = True
                elif other_passed:
                    other_passed = "cleared"
                yield_hold = plan["ego_precedence_request"] == "yield" and other_passed != "cleared"
                lane_action = plan["ego_lane_action_request"]
                if lane_action in ("stop","stand","park") and intersects(ego_body,facility):
                    if lane_hold_start is None:
                        lane_hold_start = index
                hold_length = {"stop":40,"stand":100,"park":200}.get(lane_action,0)
                action_hold = lane_hold_start is not None and index-lane_hold_start < hold_length
                ego_command = control((ego_location.x,ego_location.y),math.radians(ego_transform.rotation.yaw),
                                      ego_speed,plan["ego_route"],hold=yield_hold or action_hold,
                                      park=lane_action == "park" and action_hold)
                ego.apply_control(self.carla.VehicleControl(**{k:v for k,v in ego_command.items() if k != "route_complete"}))
                other_hold = plan["ego_precedence_request"] == "proceed_first" and index < 100
                other_command = control((other_location.x,other_location.y),math.radians(other_transform.rotation.yaw),
                                        other_speed,plan["participant_route"],target_speed=3.0,hold=other_hold)
                if plan["participant_kind"].endswith("pedestrian"):
                    target = plan["participant_route"][-1]
                    angle = math.atan2(target[1]-other_location.y,target[0]-other_location.x)
                    other.apply_control(self.carla.WalkerControl(
                        direction=self.carla.Vector3D(x=math.cos(angle),y=math.sin(angle)),
                        speed=0.0 if other_hold else 1.5))
                else:
                    other.apply_control(self.carla.VehicleControl(**{k:v for k,v in other_command.items() if k != "route_complete"}))
                frame = self.world.tick()
                for name,pending in self.sensors.items():
                    image = pending.get(timeout=20)
                    if image.frame != frame:
                        raise ValueError("original four-camera frame join differs")
                    folder = self.output/"capture"/name
                    folder.mkdir(parents=True,exist_ok=True)
                    image.save_to_disk(str(folder/f"{index:06d}.png"))
                ego_body,ego_vertices = body_polygon(ego)
                other_body,other_vertices = body_polygon(other)
                time_s = index/20
                history.append({"frame":frame,"time_s":time_s,"ego_actor_id":ego.id,
                                "participant_actor_id":other.id,"rider_actor_id":rider.id if rider else None,
                                "ego_body_polygon":ego_body,"participant_body_polygon":other_body,
                                "ego_lane_action_request":lane_action,"ego_control":ego_command,
                                "participant_control":other_command})
                ego_transform = ego.get_transform()
                ego_location = ego_transform.location
                ego_velocity = ego.get_velocity()
                trace.write(json.dumps({"frame":frame,"time_s":time_s,
                    "position_m":[ego_location.x,ego_location.y,ego_location.z],
                    "speed_mps":math.hypot(ego_velocity.x,ego_velocity.y),
                    "heading_deg":ego_transform.rotation.yaw,"control":ego_command})+"\n")
                frame_map.write(json.dumps({"video_frame":index,"carla_frame":frame,
                                            "native_frame":frame,"time_s":time_s})+"\n")
                other_transform=other.get_transform()
                other_velocity=other.get_velocity()
                other_speed=math.sqrt(other_velocity.x**2+other_velocity.y**2+other_velocity.z**2)
                observed = {"frame":frame,"time_s":time_s,
                    "participants":[{"actor_id":other.id,
                        "blueprint":other.type_id,
                        "blueprint_attributes":dict(other.attributes),
                        "heading_deg":other_transform.rotation.yaw,
                        "speed_mps":other_speed,
                        "velocity_mps":[other_velocity.x,other_velocity.y,other_velocity.z],
                        "body_vertices_m":[[v.x,v.y,v.z] for v in other_vertices]}],
                    "map_context":{"cycle_facility_id":plan["facility_id"]}}
                if rider is not None:
                    rider_transform=rider.get_transform()
                    rider_velocity=rider.get_velocity()
                    rider_vertices=rider.bounding_box.get_world_vertices(rider_transform)
                    rider_speed=math.sqrt(rider_velocity.x**2+rider_velocity.y**2+rider_velocity.z**2)
                    observed["participants"].append({
                        "actor_id":rider.id,"blueprint":rider.type_id,
                        "blueprint_attributes":dict(rider.attributes),
                        "heading_deg":rider_transform.rotation.yaw,
                        "speed_mps":rider_speed,
                        "velocity_mps":[rider_velocity.x,rider_velocity.y,rider_velocity.z],
                        "body_vertices_m":[[v.x,v.y,v.z] for v in rider_vertices]})
                evidence.write(json.dumps({"original_frame":frame,"replay_frame":frame,
                    "actor_id":ego.id,"recording_time_s":time_s,
                    "replay_simulation_time_s":time_s,"world":{"weather":{}},
                    "ego":{"position_m":[ego_location.x,ego_location.y,ego_location.z],
                           "heading_deg":ego_transform.rotation.yaw,
                           "speed_mps":math.hypot(ego_velocity.x,ego_velocity.y),
                           "speed_provenance":"original_native_readback",
                           "body_vertices_m":[[v.x,v.y,v.z] for v in ego_vertices]},
                    "original_observations":observed})+"\n")
                graph_rel=f"graphs/base/{index:08d}.adapter.json"
                graph=self.output/"capture/native"/graph_rel
                graph.parent.mkdir(parents=True,exist_ok=True)
                graph.write_text(json.dumps({"path":"capture/native/"+graph_rel,
                    "attributes":{"frame":frame,"time_s":time_s,"observed_evidence":observed},
                    "nodes":[],"edges":[]})+"\n")
                native_index.write(json.dumps({"frame":frame,"simulation_time":time_s,
                                               "adapter_graph":graph_rel})+"\n")
        (self.output/"history.json").write_text(json.dumps(history)+"\n")
        (self.output/"capture/manifest.json").write_text(json.dumps({
            "status":"draft","acquisition":"original_native","case_id":config["selected_case_id"],
            "frames":900,"extraction_confirmed":True,"complete_driving_lanes":False,
            "sources":{"road.xodr":sha(self.road),"trace.jsonl":sha(trace_path)}})+"\n")
        cameras={}
        for name in VIEWS:
            folder=self.output/"capture"/name
            target=self.output/(name+".mkv")
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                "-framerate","20","-start_number","0","-i",str(folder/"%06d.png"),
                "-frames:v","900","-c:v","ffv1","-pix_fmt","bgr0",str(target)],
                check=True,timeout=600)
            cameras[name]={"path":target.name,"sha256":sha(target)}
        references={}
        for name,path in self.sources.items():
            target=self.output/(name+"-source.json")
            shutil.copy2(path,target)
            references[name]={"path":target.name,"sha256":sha(target)}
        shutil.copy2(self.road,self.output/"road.xodr")
        (self.output/"attempt-source.json").write_text(json.dumps({
            "format":"cycle-lane-2703-native-attempt-v1","source_kind":"original_native",
            "diagnostic_fixture":False,"case_id":config["selected_case_id"],
            "ego_actor_id":ego.id,"participant_actor_id":other.id,
            "rider_actor_id":rider.id if rider else None,
            "sources":references,"history":{"path":"history.json","sha256":sha(self.output/"history.json")},
            "cameras":cameras,"capture_profile":plan["capture_profile"]},indent=2)+"\n")

    def close(self):
        errors=[]
        for actor in reversed(self.owned):
            try:
                if hasattr(actor,"stop"):
                    actor.stop()
                actor.destroy()
            except Exception as error:
                errors.append(repr(error))
        if self.recorder_started:
            try:
                self.client.stop_recorder()
                info=self.client.show_recorder_file_info(str(self.output/"carla_recorder.log"),False)
                (self.output/"capture/recorder_info.txt").write_text(info)
            except Exception as error:
                errors.append(repr(error))
        try:
            self.world.apply_settings(self.old_settings)
            restored=self.world.get_settings()
            self.restoration_verified=(not errors and
                restored.synchronous_mode == self.old_settings.synchronous_mode and
                restored.fixed_delta_seconds == self.old_settings.fixed_delta_seconds)
        except Exception as error:
            errors.append(repr(error))
            self.restoration_verified=False
        if not self.restoration_verified:
            raise ValueError("Native restoration unverified: "+repr(errors))
