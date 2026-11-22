import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_capture


class Actor:
    def __init__(self, ident, x, y):
        self.id, self.x, self.y = ident, x, y
        self.control = {"brake": 1, "throttle": 0}
        self.destroyed = False
        self.bounding_box = self
    def get_world_vertices(self, transform):
        return [types.SimpleNamespace(x=self.x+dx, y=self.y+dy)
                for _ in (0,1) for dx,dy in ((-.1,-.1),(.1,-.1),(.1,.1),(-.1,.1))]
    def get_transform(self):
        return types.SimpleNamespace(location=types.SimpleNamespace(x=self.x,y=self.y),
                                     rotation=types.SimpleNamespace(yaw=0))
    def get_velocity(self): return types.SimpleNamespace(x=0,y=0)
    def apply_control(self, value): self.control = value
    def destroy(self): self.destroyed = True


class NativeRunTests(unittest.TestCase):
    def test_joined_capture_and_restoration_before_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ego, other = Actor(11,-2,0), Actor(22,0,-2)
            class Settings:
                def __init__(self, sync=False, delta=None):
                    self.synchronous_mode=sync; self.fixed_delta_seconds=delta
            class Map:
                def to_opendrive(self): return "map"
            class World:
                def __init__(self): self.settings=Settings(); self.frame=0; self.restored=False
                def get_settings(self):
                    return Settings(self.settings.synchronous_mode,self.settings.fixed_delta_seconds)
                def apply_settings(self, value):
                    self.settings=Settings(value.synchronous_mode,value.fixed_delta_seconds)
                    if not value.synchronous_mode: self.restored=True
                def get_map(self): return Map()
                def tick(self):
                    self.frame += 1
                    other.y = (-2,0,2,2,2,2)[self.frame-1]
                    if ego.control["throttle"]: ego.x = 0 if ego.x < 0 else 2
                    return self.frame
                def get_snapshot(self):
                    return types.SimpleNamespace(frame=self.frame,
                        timestamp=types.SimpleNamespace(elapsed_seconds=self.frame/20))
            world=World()
            class Client:
                def __init__(self,host,port): pass
                def set_timeout(self,seconds): pass
                def get_world(self): return world
            carla=types.ModuleType("carla")
            carla.Client=Client
            carla.VehicleControl=lambda **kw: kw
            class Capture:
                def __init__(self,client,ego,output,case_id):
                    self.path=Path(output)/"trace.jsonl"
                    self.path.touch()
                    (Path(output)/"road.xodr").write_text("map")
                    (Path(output)/"carla_recorder.log").write_text("recorder")
                def capture(self,frame,time_s):
                    with self.path.open("a") as stream:
                        stream.write(json.dumps({"frame":frame,"time_s":time_s})+"\n")
                def close(self): pass
            pipeline=types.ModuleType("pipeline_capture"); pipeline.PipelineCapture=Capture
            class FrameMap:
                def __init__(self,path): self.path=Path(path);self.path.touch();self.index=0
                def append(self,frame,time_s):
                    with self.path.open("a") as stream:
                        stream.write(json.dumps({"carla_frame":frame,"native_frame":frame,
                                                 "video_frame":self.index,"time_s":time_s})+"\n")
                    self.index+=1
                def close(self): pass
            sealed=[]
            def seal(path, **kw):
                self.assertTrue(world.restored)
                self.assertTrue(ego.destroyed and other.destroyed)
                sealed.append(kw)
            exchange=types.ModuleType("worker_exchange")
            native_output=types.ModuleType("worker_exchange.native_output")
            native_output.FrameMap=FrameMap; native_output.seal_capture=seal
            restore=types.ModuleType("worker_exchange.world_restore")
            restore.fields=lambda obj: vars(obj)
            restore.equal=lambda a,b: a==b
            class Cameras:
                SPECS=native_capture.CameraBank.SPECS
                def __init__(self,world,ego,output,carla,scene):
                    for name,*_ in self.SPECS:
                        (Path(output)/(name+".mkv")).write_bytes(b"fake video")
                def append(self,frame): pass
                def close(self): pass
            crossing={"crossing_id":"crossing", "roadway_id":"west",
                      "bounds_xy_m":[-1,-1,1,1],
                      "map_source_sha256":hashlib.sha256(b"map").hexdigest()}
            law={"map_source":crossing["map_source_sha256"],"ego_highway":"A",
                 "other_highway":"B","public_access_source":"review","device_inventory_source":"review",
                 "driver_scope_source":"review","public_access":True,"human_driver":True,
                 "devices":[],"approach_relation":"crossing","left_turn_intent":False,
                 "left_turn_realized":False}
            for key, relative in native_capture.REVIEW_SOURCES.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic source for " + key)
                law[key] = {"source_path": key + ".txt",
                            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "reviewer": "fixture", "source_citation": "fixture only"}
            packet={"crossing":crossing,"law_context":law}
            def review(scene,output,world):
                (Path(output)/"reviewed-context.json").write_text(json.dumps(packet))
                return packet
            scene={"case_id":"C125714","capture_rate_hz":20,"duration_s":.3,
                   "crossing":crossing,"other_route_xy_m":[[0,-3],[0,0],[0,3]],
                   "ego_route_xy_m":[[-3,0],[0,0],[3,0]],"other_entered_first":True}
            modules={"carla":carla,"pipeline_capture":pipeline,"worker_exchange":exchange,
                     "worker_exchange.native_output":native_output,
                     "worker_exchange.world_restore":restore}
            with patch.dict(sys.modules,modules), \
                 patch.object(native_capture,"reviewed_context",side_effect=review), \
                 patch.object(native_capture,"spawn_vehicles",return_value={"ego":ego,"other":other}), \
                 patch.object(native_capture,"CameraBank",Cameras):
                native_capture.run_native(scene,root,"localhost",2000)
            ego_rows=[json.loads(line) for line in (root/"ego-body-history.jsonl").read_text().splitlines()]
            other_rows=[json.loads(line) for line in (root/"other-body-history.jsonl").read_text().splitlines()]
            self.assertEqual([r["frame"] for r in ego_rows],list(range(1,7)))
            self.assertEqual([r["time_s"] for r in ego_rows],[r["time_s"] for r in other_rows])
            self.assertEqual(ego_rows[-1]["body_vertices_xy_m"][0][0],1.9)
            self.assertEqual(len(sealed),1)
            self.assertEqual(sealed[0]["frames"],6)
            acquisition=json.loads((root/"acquisition.json").read_text())
            self.assertEqual(acquisition["other-body-history.jsonl"]["sha256"],
                             native_capture.sha(root/"other-body-history.jsonl"))


if __name__ == "__main__": unittest.main()
