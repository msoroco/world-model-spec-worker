import importlib.util
import hashlib
import json
import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


measure=load("signal_exception_measurements")
control=load("signal_control")


def body(x):return [[x+dx,y] for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]


class SignalTests(unittest.TestCase):
    def fixture(self,root,controls=True,state="Green"):
        ctx={"native_map_id":"TownX","intersection_id":44,"ego_road_id":7,
             "ego_lane_id":-1,"native_signal_id":25,
             "ego_route_lanes":[[7,-1],[8,-1]],
             "affected_lane_source":"native-affected-waypoints",
             "signal_head_video_source":"front-original",
             "signed_entrance_source":"native-sign-and-camera",
             "junction_source":"native-polygon",
             "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
        (root/"signal_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,x in enumerate((0,0,12)):
            rows.append({"frame":100+i,"time_s":1+i*.05,"native_signal_id":25,
                         "ego_road_id":8 if i==2 else 7,"ego_lane_id":-1,"signal_state":state,
                         "signal_controls_ego":controls,"ego_speed_mps":2,
                         "ego_body_vertices_xy_m":body(x)})
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"],
                 "camera_frames":{name:r["frame"] for name in control.CAMERAS}}
                for i,r in enumerate(rows)]
        (root/"signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_active_governing_signal_at_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            self.assertTrue(measure.analyze(root)["operative_signal_controls_ego_at_entry_observed"])
            self.fixture(root,controls=False)
            self.assertFalse(measure.analyze(root)["operative_signal_controls_ego_at_entry_observed"])
            self.fixture(root,state="Off")
            self.assertFalse(measure.analyze(root)["operative_signal_controls_ego_at_entry_observed"])

    def test_stale_join_and_wrong_light_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):measure.analyze(root)
            self.fixture(root)
            rows=[json.loads(r) for r in (root/"signal_history.jsonl").read_text().splitlines()]
            rows[2]["native_signal_id"]=999
            (root/"signal_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
            with self.assertRaisesRegex(ValueError,"light identity"):measure.analyze(root)

    def test_native_governing_light_selection_and_reversible_state(self):
        class Actors(list):
            def filter(self,pattern):return self
        class Light:
            def __init__(self,road):self.road,self.state=road,"Green"
            def get_affected_lane_waypoints(self):return [NS(road_id=self.road,lane_id=-1)]
            def get_state(self):return self.state
            def set_state(self,value):self.state=value
            def freeze(self,value):self.frozen=value
        selected=Light(7);other=Light(9)
        world=NS(get_actors=lambda:Actors([other,selected]),tick=lambda:None)
        self.assertIs(control.find_governing_signal(world,7,-1),selected)
        with control.SignalControl(world,selected,NS(Red="Red",Green="Green",Off="Off"),"Red"):
            self.assertEqual(selected.state,"Red")
        self.assertEqual(selected.state,"Green")
        self.assertFalse(selected.frozen)

    def test_native_pair_construction_distinguishes_governing_and_other_head(self):
        class Actors(list):
            def filter(self, pattern):return self
        class Vehicle:
            def __init__(self, lane):self.lane,self.destroyed=lane,False
            def get_location(self):return self
            def destroy(self):self.destroyed=True
        class Light:
            def __init__(self, id, lane):self.id,self.lane,self.state=id,lane,"Green"
            def get_affected_lane_waypoints(self):return [NS(road_id=self.lane[0],lane_id=self.lane[1])]
            def get_state(self):return self.state
            def set_state(self, value):self.state=value
            def freeze(self, value):self.frozen=value
        vehicles=[Vehicle([7,-1]),Vehicle([9,-1])]
        governing,other=Light(25,[7,-1]),Light(26,[11,-1])
        native_map=NS(name="TownX",get_waypoint=lambda location,project_to_road:NS(
            road_id=location.lane[0],lane_id=location.lane[1]))
        world=NS(get_map=lambda:native_map,get_actors=lambda:Actors([governing,other]),
                 try_spawn_actor=lambda blueprint,transform:vehicles.pop(0),tick=lambda:None)
        site={"native_map_id":"TownX","approach_lanes":{"ego":[7,-1],"through":[9,-1]}}
        states=NS(Red="Red",Green="Green",Off="Off")
        first=Vehicle([7,-1]);second=Vehicle([9,-1]);vehicles[:]=[first,second]
        with control.construct_signal_comparison(world,site,{"ego":"car","through":"car"},
                                                 {"ego":"pose1","through":"pose2"},
                                                 states,"Red",25,True) as built:
            self.assertTrue(built["signal_controls_ego"])
            self.assertEqual(governing.state,"Red")
            self.assertFalse(built["legal_exception_verified"])
        self.assertEqual(governing.state,"Green")
        self.assertTrue(first.destroyed and second.destroyed)
        first=Vehicle([7,-1]);second=Vehicle([9,-1]);vehicles[:]=[first,second]
        with control.construct_signal_comparison(world,site,{"ego":"car","through":"car"},
                                                 {"ego":"pose1","through":"pose2"},
                                                 states,"Red",26,False) as built:
            self.assertFalse(built["signal_controls_ego"])
        self.assertEqual(other.state,"Green")
        first=Vehicle([7,-1]);second=Vehicle([9,-1]);vehicles[:]=[first,second]
        with self.assertRaisesRegex(ValueError,"governance differs"):
            with control.construct_signal_comparison(world,site,{"ego":"car","through":"car"},
                                                     {"ego":"pose1","through":"pose2"},
                                                     states,"Red",26,True):pass
        self.assertTrue(first.destroyed and second.destroyed)
        first=Vehicle([7,-1]);second=Vehicle([8,-1]);vehicles[:]=[first,second]
        with self.assertRaisesRegex(ValueError,"outside selected approach lane"):
            with control.construct_signal_comparison(world,site,{"ego":"car","through":"car"},
                                                     {"ego":"pose1","through":"pose2"},
                                                     states,"Red",25,True):pass
        self.assertTrue(first.destroyed and second.destroyed)

    def test_source_writer_joins_four_original_cameras_and_rejects_stale_packets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ctx={"native_map_id":"TownX","intersection_id":44,"ego_road_id":7,
                 "ego_lane_id":-1,"through_road_id":9,"through_lane_id":-1,
                 "native_signal_id":25,
                 "ego_route_lanes":[[7,-1],[8,-1]],
                 "affected_lane_source":"Native affected waypoints",
                 "signal_head_video_source":"approach.mkv",
                 "signed_entrance_source":"reference_corner.mkv",
                 "junction_source":"Native map junction polygon",
                 "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
            writer=control.SignalSourceWriter(root,ctx)
            clock={"frame":100,"time":1.0,"x":0.0}
            world=NS(get_snapshot=lambda:NS(frame=clock["frame"],timestamp=NS(
                elapsed_seconds=clock["time"])),get_map=lambda:NS(name="TownX",
                get_waypoint=lambda location,project_to_road:NS(road_id=7,lane_id=-1)))
            ego=NS(get_transform=lambda:NS(location=NS(x=clock["x"])),
                   get_velocity=lambda:NS(x=2.0,y=0.0,z=0.0),
                   bounding_box=NS(get_world_vertices=lambda transform:[NS(x=clock["x"]+dx,y=y)
                   for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]))
            light=NS(id=25,get_state=lambda:"Green",get_affected_lane_waypoints=lambda:[
                NS(road_id=7,lane_id=-1)])
            def packets():
                return {name:NS(frame=clock["frame"],timestamp=clock["time"],
                                raw_data=b"rgba",width=1,height=1)
                        for name in control.CAMERAS}
            for frame,time_s,x in ((100,1.0,0.0),(101,1.05,0.0),(102,1.1,12.0)):
                clock.update(frame=frame,time=time_s,x=x)
                p=packets()
                if frame==101:
                    p["approach"].frame=100
                    with self.assertRaisesRegex(ValueError,"Camera frame"):
                        writer.add_tick(world,ego,light,p,True)
                    self.assertEqual(writer.count,1)
                    p=packets()
                writer.add_tick(world,ego,light,p,True)
            self.assertTrue(measure.analyze(root)["operative_signal_controls_ego_at_entry_observed"])
            with self.assertRaisesRegex(ValueError,"Nonmonotone"):
                writer.add_tick(world,ego,light,packets(),True)
            self.assertEqual(len((root/"signal_history.jsonl").read_text().splitlines()),3)
            with self.assertRaisesRegex(ValueError,"already exists"):
                control.SignalSourceWriter(root,ctx)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[2]["camera_frames"]["approach"]=101
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"Four original camera frame joins"):
                measure.analyze(root)

    def test_four_original_camera_streams_encode_losslessly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sizes={name:(2,2) for name in control.CAMERAS}
            with control.FourCameraEncoder(root,sizes) as encoder:
                for frame in range(3):
                    packets={name:NS(width=2,height=2,raw_data=bytes([frame,0,0,255])*4)
                             for name in control.CAMERAS}
                    encoder.add_packets(packets)
                self.assertEqual(encoder.count,3)
            for name in control.CAMERAS:
                proc=subprocess.run(["ffprobe","-v","error","-count_frames","-select_streams","v:0",
                    "-show_entries","stream=codec_name,nb_read_frames","-of","json",
                    str(root/(name+".mkv"))],capture_output=True,text=True,check=True)
                stream=json.loads(proc.stdout)["streams"][0]
                self.assertEqual(stream["codec_name"],"ffv1")
                self.assertEqual(stream["nb_read_frames"],"3")
                decoded=subprocess.run(["ffmpeg","-v","error","-i",str(root/(name+".mkv")),
                    "-f","rawvideo","-pix_fmt","bgra","pipe:1"],capture_output=True,check=True)
                self.assertEqual(decoded.stdout,b"".join(bytes([frame,0,0,255])*4
                                                     for frame in range(3)))
            with self.assertRaisesRegex(ValueError,"already exists"):
                with control.FourCameraEncoder(root,sizes):pass

    def test_native_capture_owns_four_sensors_and_saved_sources(self):
        class Sensor:
            def __init__(self,name):self.name,self.stopped,self.destroyed=name,False,False
            def listen(self,callback):self.callback=callback
            def stop(self):self.stopped=True
            def destroy(self):self.destroyed=True
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ctx={"native_map_id":"TownX","intersection_id":44,"ego_road_id":7,
                 "ego_lane_id":-1,"through_road_id":9,"through_lane_id":-1,
                 "native_signal_id":25,
                 "ego_route_lanes":[[7,-1],[8,-1]],"through_route_lanes":[[9,-1]],
                 "affected_lane_source":"Native affected waypoints",
                 "signal_head_video_source":"approach.mkv",
                 "signed_entrance_source":"reference_corner.mkv",
                 "junction_source":"Native polygon",
                 "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
            (root/"config.json").write_text(json.dumps({
                "selected_case_id":"testing__C158196__NRS-484B-257-1__motor_vehicle_driver__signal_controls_ego",
                "law_id":"NRS-484B-257-1","cell_id":"C158196",
                "recording_description":{"channels":[]}}))
            clock={"frame":99,"x":0.0,"stale":False}
            sensors={}
            def spawn(name,transform,**options):
                sensor=Sensor(name);sensors[name]=sensor;return sensor
            def tick():
                clock["frame"]+=1
                clock["x"]=12.0 if clock["frame"]>=102 else 0.0
                for name,sensor in sensors.items():
                    fid=clock["frame"]-1 if clock["stale"] and name=="approach" else clock["frame"]
                    sensor.callback(NS(frame=fid,timestamp=clock["frame"]*.05,
                                       raw_data=bytes([clock["frame"]%255,0,0,255]),
                                       width=1,height=1))
                return clock["frame"]
            world=NS(spawn_actor=spawn,tick=tick,get_snapshot=lambda:NS(
                frame=clock["frame"],timestamp=NS(elapsed_seconds=clock["frame"]*.05)),
                get_map=lambda:NS(name="TownX",get_waypoint=lambda location,project_to_road:
                                  NS(road_id=location.road_id,lane_id=-1)))
            ego=NS(get_transform=lambda:NS(location=NS(x=clock["x"],
                                           road_id=8 if clock["x"]>=10 else 7)),
                   get_velocity=lambda:NS(x=2.0,y=0.0,z=0.0),
                   bounding_box=NS(get_world_vertices=lambda transform:[NS(x=clock["x"]+dx,y=y,z=0.0)
                   for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]))
            through=NS(get_transform=lambda:NS(location=NS(x=15.0,road_id=9)),
                       bounding_box=NS(get_world_vertices=lambda transform:[
                           NS(x=15.0+dx,y=y,z=0.0)
                           for dx,y in ((-1,-1),(-1,1),(1,1),(1,-1))]))
            light=NS(id=25,get_state=lambda:"Green",get_affected_lane_waypoints=lambda:[
                NS(road_id=7,lane_id=-1)])
            captures=[]
            class FakePipelineCapture:
                def __init__(self,client,ego,output,case_id,required_observations):
                    self.root=Path(output);self.rows=[];self.closed=None
                    self.asserted_case=case_id
                    (self.root/"road.xodr").write_text("<OpenDRIVE/>")
                    (self.root/"capture").mkdir()
                    captures.append(self)
                def capture(self,frame,time_s):
                    self.rows.append({"frame":frame,"time_s":time_s,
                        "position":{"x":clock["x"],"y":0.0,"z":0.0},
                        "heading_deg":0.0,"speed_mps":2.0})
                    (self.root/"trace.jsonl").write_text("".join(json.dumps(row)+"\n"
                                                    for row in self.rows))
                    with (self.root/"capture/evidence.jsonl").open("a") as stream:
                        stream.write(json.dumps({"original_frame":frame})+"\n")
                def close(self,confirmed):self.closed=confirmed
            mounts={name:{"transform":name,"attach_to":None if name=="overview" else "ego"}
                    for name in control.CAMERAS}
            with control.NativeSignalCapture(world,root,{"ego":ego,"through":through},light,
                    ctx,True,{name:name for name in control.CAMERAS},mounts,
                    object(),"selected-signal-case",[],sizes={name:(1,1) for name in control.CAMERAS},
                    capture_factory=FakePipelineCapture) as session:
                for _ in range(3):session.capture_tick()
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in sensors.values()))
            self.assertEqual(captures[-1].closed,True)
            self.assertEqual(len((root/"trace.jsonl").read_text().splitlines()),3)
            self.assertEqual(len((root/"interaction_history.jsonl").read_text().splitlines()),3)
            self.assertTrue(measure.analyze(root)["operative_signal_controls_ego_at_entry_observed"])
            self.assertTrue(all((root/(name+".mkv")).is_file() for name in control.CAMERAS))
            review={"method":"original_source_camera_frame_review",
                    "case_id":json.loads((root/"config.json").read_text())["selected_case_id"],
                    "reviewer":"diagnostic-fixture-reviewer",
                    "reviewed_carla_frames":[100,101,102],
                    "camera_sha256":{name:hashlib.sha256((root/(name+".mkv")).read_bytes()).hexdigest()
                                     for name in control.CAMERAS},
                    "observations":{"signed_entrance_visible":True,
                                    "signal_head_visible":True,"head_at_ego_approach":True}}
            (root/"signal_head_review.json").write_text(json.dumps(review))
            with tempfile.TemporaryDirectory() as stale:
                negative=Path(stale)
                for source in root.iterdir():
                    if source.is_file():shutil.copy2(source,negative/source.name)
                    elif source.name=="capture":shutil.copytree(source,negative/source.name)
                (negative/"signal_head_review.json").unlink()
                with self.assertRaisesRegex(ValueError,"Missing required source: signal_head_review.json"):
                    measure.finalize(negative,negative/"analysis-report.json")
                review["camera_sha256"]["approach"]="0"*64
                (negative/"signal_head_review.json").write_text(json.dumps(review))
                with self.assertRaisesRegex(ValueError,"Original-camera review source hash differs"):
                    measure.finalize(negative,negative/"analysis-report.json")
                review["camera_sha256"]["approach"]=hashlib.sha256((root/"approach.mkv").read_bytes()).hexdigest()
                subprocess.run(["ffmpeg","-v","error","-i",str(root/"overview.mkv"),
                                "-frames:v","2","-c:v","ffv1",str(negative/"short.mkv")],check=True)
                (negative/"short.mkv").replace(negative/"overview.mkv")
                review["camera_sha256"]["overview"]=hashlib.sha256((negative/"overview.mkv").read_bytes()).hexdigest()
                (negative/"signal_head_review.json").write_text(json.dumps(review))
                with self.assertRaisesRegex(ValueError,"decoded frame count or codec differs"):
                    measure.finalize(negative,negative/"analysis-report.json")
            analysis=measure.finalize(root,root/"analysis-report.json")
            self.assertEqual(analysis["source_camera_review"]["reviewer"],"diagnostic-fixture-reviewer")
            self.assertTrue(analysis["measurements"]["operative_signal_at_entry"]["value"])
            self.assertEqual(len((root/"channels/operative_signal_control.jsonl").read_text().splitlines()),3)
            self.assertFalse(json.loads((root/"result.json").read_text())["physical_acceptance_claimed"])
            with tempfile.TemporaryDirectory() as missing:
                negative=Path(missing)
                for source in root.iterdir():
                    if source.is_file() and source.name not in ("result.json","analysis-report.json",
                                                                 "signal_history.jsonl"):
                        shutil.copy2(source,negative/source.name)
                    elif source.name=="capture":
                        shutil.copytree(source,negative/source.name)
                with self.assertRaisesRegex(ValueError,"Missing required source: signal_history.jsonl"):
                    measure.finalize(negative,negative/"analysis-report.json")
        with tempfile.TemporaryDirectory() as other_tmp:
            other_root=Path(other_tmp)
            clock.update(frame=99,x=0.0,stale=False)
            sensors.clear()
            other_ctx=dict(ctx)
            other_ctx["native_signal_id"]=26
            other_ctx["signal_head_video_source"]="reference_corner.mkv"
            other_light=NS(id=26,get_state=lambda:"Green",
                           get_affected_lane_waypoints=lambda:[NS(road_id=11,lane_id=-1)])
            other_case="testing__C158196__NRS-484B-257-1__motor_vehicle_driver__signal_visible_not_governing"
            other_config={"selected_case_id":other_case,"law_id":"NRS-484B-257-1",
                          "cell_id":"C158196","recording_description":{"channels":[]}}
            (other_root/"config.json").write_text(json.dumps(other_config))
            with control.NativeSignalCapture(world,other_root,{"ego":ego,"through":through},
                    other_light,other_ctx,False,{name:name for name in control.CAMERAS},mounts,
                    object(),other_case,[],sizes={name:(1,1) for name in control.CAMERAS},
                    capture_factory=FakePipelineCapture) as session:
                for _ in range(3):session.capture_tick()
            self.assertFalse(measure.analyze(other_root)["operative_signal_controls_ego_at_entry_observed"])
            other_review={"method":"original_source_camera_frame_review",
                          "case_id":other_case,"reviewer":"diagnostic-fixture-reviewer",
                          "reviewed_carla_frames":[100,101,102],
                          "camera_sha256":{name:hashlib.sha256((other_root/(name+".mkv")).read_bytes()).hexdigest()
                                           for name in control.CAMERAS},
                          "observations":{"signed_entrance_visible":True,
                                          "signal_head_visible":True,
                                          "head_at_ego_approach":False}}
            (other_root/"signal_head_review.json").write_text(json.dumps(other_review))
            frames=[json.loads(line) for line in (other_root/"video_frames.jsonl").read_text().splitlines()]
            other_review["observations"]["head_at_ego_approach"]=True
            (other_root/"signal_head_review.json").write_text(json.dumps(other_review))
            with self.assertRaisesRegex(ValueError,"Case-specific original-camera visual observations differ"):
                measure.validate_source_camera_review(other_root,frames,other_case)
            other_review["observations"]["head_at_ego_approach"]=False
            (other_root/"signal_head_review.json").write_text(json.dumps(other_review))
            other_analysis=measure.finalize(other_root,other_root/"analysis-report.json")
            self.assertFalse(other_analysis["measurements"]["operative_signal_at_entry"]["value"])
            other_result=json.loads((other_root/"result.json").read_text())
            self.assertTrue(other_result["target_checks"][0]["matched"])
            self.assertFalse(other_result["physical_acceptance_claimed"])
        with tempfile.TemporaryDirectory() as off_tmp:
            off_root=Path(off_tmp)
            clock.update(frame=99,x=0.0,stale=False)
            sensors.clear()
            off_case="testing__C158196__NRS-484B-257-1__motor_vehicle_driver__signal_off"
            off_config={"selected_case_id":off_case,"law_id":"NRS-484B-257-1",
                        "cell_id":"C158196","recording_description":{"channels":[]}}
            (off_root/"config.json").write_text(json.dumps(off_config))
            off_light=NS(id=25,get_state=lambda:"Off",get_affected_lane_waypoints=lambda:[
                NS(road_id=7,lane_id=-1)])
            with control.NativeSignalCapture(world,off_root,{"ego":ego,"through":through},
                    off_light,ctx,True,{name:name for name in control.CAMERAS},mounts,
                    object(),off_case,[],sizes={name:(1,1) for name in control.CAMERAS},
                    capture_factory=FakePipelineCapture) as session:
                for _ in range(3):session.capture_tick()
            off_review={"method":"original_source_camera_frame_review",
                        "case_id":off_case,"reviewer":"diagnostic-fixture-reviewer",
                        "reviewed_carla_frames":[100,101,102],
                        "camera_sha256":{name:hashlib.sha256((off_root/(name+".mkv")).read_bytes()).hexdigest()
                                         for name in control.CAMERAS},
                        "observations":{"signed_entrance_visible":True,
                                        "signal_head_visible":True,
                                        "head_at_ego_approach":True}}
            (off_root/"signal_head_review.json").write_text(json.dumps(off_review))
            off_analysis=measure.finalize(off_root,off_root/"analysis-report.json")
            self.assertFalse(off_analysis["measurements"]["operative_signal_at_entry"]["value"])
            self.assertEqual(off_analysis["measurements"]["entry_signal_state"]["value"],"Off")
            off_result=json.loads((off_root/"result.json").read_text())
            self.assertTrue(off_result["target_checks"][0]["matched"])
            self.assertFalse(off_result["physical_acceptance_claimed"])
        signal_state={"value":"Green"}
        light.get_state=lambda:signal_state["value"]
        light.set_state=lambda value:signal_state.update(value=value)
        light.freeze=lambda value:None
        owned={"ego":False,"through":False}
        ego.get_location=lambda:ego.get_transform().location
        through.get_location=lambda:through.get_transform().location
        ego.destroy=lambda:owned.update(ego=True)
        through.destroy=lambda:owned.update(through=True)
        world.get_actors=lambda:NS(filter=lambda pattern:[light])
        world.try_spawn_actor=lambda blueprint,transform:{"ego":ego,"through":through}[blueprint]
        site={"native_map_id":"TownX","approach_lanes":{"ego":[7,-1],"through":[9,-1]}}
        states=NS(Red="Red",Green="Green",Off="Off")
        with tempfile.TemporaryDirectory() as integrated_tmp:
            clock.update(frame=99,x=0.0,stale=False)
            sensors.clear()
            driven=[]
            summary=control.run_signal_capture(world,object(),integrated_tmp,site,
                    {"ego":"ego","through":"through"},{"ego":"pose1","through":"pose2"},
                    states,"Red",25,True,ctx,{name:name for name in control.CAMERAS},mounts,
                    "selected-signal-case",[],lambda index,actors:driven.append(index),3,
                    sizes={name:(1,1) for name in control.CAMERAS},
                    capture_factory=FakePipelineCapture)
            self.assertEqual(driven,[0,1,2])
            self.assertEqual(summary["source_frames"],3)
            self.assertEqual(len((Path(integrated_tmp)/"trace.jsonl").read_text().splitlines()),3)
            self.assertTrue(measure.analyze(Path(integrated_tmp))["operative_signal_controls_ego_at_entry_observed"])
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in sensors.values()))
            self.assertTrue(all(owned.values()))
            self.assertEqual(signal_state["value"],"Green")
        with tempfile.TemporaryDirectory() as aborted_tmp:
            clock.update(frame=99,x=0.0,stale=False)
            sensors.clear()
            owned.update(ego=False,through=False)
            def reject_drive(index,actors):
                raise ValueError("diagnostic drive failure")
            with self.assertRaisesRegex(ValueError,"diagnostic drive failure"):
                control.run_signal_capture(world,object(),aborted_tmp,site,
                    {"ego":"ego","through":"through"},{"ego":"pose1","through":"pose2"},
                    states,"Red",25,True,ctx,{name:name for name in control.CAMERAS},mounts,
                    "selected-signal-case",[],reject_drive,3,
                    sizes={name:(1,1) for name in control.CAMERAS},
                    capture_factory=FakePipelineCapture)
            self.assertTrue(all(owned.values()))
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in sensors.values()))
            self.assertEqual(signal_state["value"],"Green")
        with tempfile.TemporaryDirectory() as tmp:
            clock.update(frame=99,x=0.0,stale=True)
            sensors.clear()
            with self.assertRaisesRegex(ValueError,"Stale or future"):
                with control.NativeSignalCapture(world,tmp,{"ego":ego,"through":through},light,
                        ctx,True,{name:name for name in control.CAMERAS},mounts,
                        object(),"selected-signal-case",[],sizes={name:(1,1) for name in control.CAMERAS},
                        capture_factory=FakePipelineCapture) as session:
                    session.capture_tick()
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in sensors.values()))
            self.assertEqual(captures[-1].closed,False)


if __name__=="__main__":unittest.main()
