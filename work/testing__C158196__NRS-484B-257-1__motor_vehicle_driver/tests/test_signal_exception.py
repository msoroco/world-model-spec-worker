import importlib.util
import json
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
             "affected_lane_source":"native-affected-waypoints",
             "signal_head_video_source":"front-original",
             "signed_entrance_source":"native-sign-and-camera",
             "junction_source":"native-polygon",
             "intersection_polygon_xy_m":[[10,-5],[20,-5],[20,5],[10,5]]}
        (root/"signal_context.json").write_text(json.dumps(ctx))
        rows=[]
        for i,x in enumerate((0,0,12)):
            rows.append({"frame":100+i,"time_s":1+i*.05,"native_signal_id":25,
                         "ego_road_id":7,"ego_lane_id":-1,"signal_state":state,
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
                 "ego_lane_id":-1,"native_signal_id":25,
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


if __name__=="__main__":unittest.main()
