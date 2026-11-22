import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import native_capture
from test_uturn_control import scene as base_scene


class NativeRunTests(unittest.TestCase):
    def test_original_frame_loop_and_restoration_before_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            class Actor:
                id=11
                def __init__(self): self.destroyed=False;self.bounding_box=self
                def get_world_vertices(self, transform):
                    return [types.SimpleNamespace(x=dx,y=-2+dy) for _ in (0,1)
                            for dx,dy in ((-.1,-.1),(.1,-.1),(.1,.1),(-.1,.1))]
                def get_transform(self):
                    return types.SimpleNamespace(location=types.SimpleNamespace(x=0,y=-2),
                                                 rotation=types.SimpleNamespace(yaw=0))
                def get_velocity(self): return types.SimpleNamespace(x=0,y=0)
                def apply_control(self, control): self.control=control
                def destroy(self): self.destroyed=True
            actor=Actor()
            class Settings:
                def __init__(self,sync=False,delta=None):
                    self.synchronous_mode=sync;self.fixed_delta_seconds=delta
            class Map:
                def to_opendrive(self): return "inspected map"
            class World:
                def __init__(self): self.settings=Settings();self.frame=0;self.restored=False
                def get_settings(self):
                    return Settings(self.settings.synchronous_mode,self.settings.fixed_delta_seconds)
                def apply_settings(self,value):
                    self.settings=Settings(value.synchronous_mode,value.fixed_delta_seconds)
                    if not value.synchronous_mode: self.restored=True
                def get_map(self): return Map()
                def tick(self): self.frame+=1;return self.frame
                def get_snapshot(self):
                    return types.SimpleNamespace(frame=self.frame,
                        timestamp=types.SimpleNamespace(elapsed_seconds=self.frame/20))
            world=World()
            class Client:
                def __init__(self,host,port): pass
                def set_timeout(self,seconds): pass
                def get_world(self): return world
            carla=types.ModuleType("carla");carla.Client=Client
            carla.VehicleControl=lambda **kw:kw
            class Capture:
                def __init__(self,client,ego,output,case_id):
                    self.path=Path(output)/"trace.jsonl";self.path.touch()
                    (Path(output)/"road.xodr").write_text("inspected map")
                    (Path(output)/"carla_recorder.log").write_text("recorder")
                def capture(self,frame,time_s):
                    with self.path.open("a") as stream:
                        stream.write(json.dumps({"frame":frame,"time_s":time_s})+"\n")
                def close(self): pass
            pipeline=types.ModuleType("pipeline_capture");pipeline.PipelineCapture=Capture
            class FrameMap:
                def __init__(self,path): self.path=Path(path);self.path.touch();self.index=0
                def append(self,frame,time_s):
                    with self.path.open("a") as stream:
                        stream.write(json.dumps({"carla_frame":frame,"video_frame":self.index,
                                                 "time_s":time_s})+"\n")
                    self.index+=1
                def close(self): pass
            seals=[]
            def seal(path,**kw):
                self.assertTrue(world.restored and actor.destroyed and
                                all(item.destroyed for item in barrier_actors))
                seals.append(kw)
            exchange=types.ModuleType("worker_exchange")
            native_output=types.ModuleType("worker_exchange.native_output")
            native_output.FrameMap=FrameMap;native_output.seal_capture=seal
            restore=types.ModuleType("worker_exchange.world_restore")
            restore.fields=lambda obj:vars(obj)
            restore.equal=lambda a,b:a==b
            class Cameras:
                SPECS=native_capture.CameraBank.SPECS
                def __init__(self,world,ego,output,carla,scene):
                    for name,*_ in self.SPECS:
                        (Path(output)/(name+".mkv")).write_bytes(b"fake video")
                def append(self,frame): pass
                def close(self): pass
            scene=base_scene()
            scene["context"].update(opening_id="opening-1",
                source_right_roadway_id="east-right",
                destination_right_roadway_id="west-right")
            scene["divider_props"]=[{"blueprint_id":"static.prop.barrier",
                "bounds_xy_m":rect,"z_m":0}
                for rect in scene["context"]["closed_divider_bounds_xy_m"]]
            scene.update(case_id="diagnostic",capture_rate_hz=20,duration_s=.3)
            def review(scene,output,world):
                (Path(output)/"reviewed-median-context.json").write_text("review")
                (Path(output)/"authority-review-source.json").write_text("authority")
                return {"context":scene["context"],"divider_props":scene["divider_props"]}
            class Barrier(Actor):
                def __init__(self,ident,rect):
                    super().__init__();self.id=ident;self.rect=rect
                def get_world_vertices(self,transform):
                    x0,y0,x1,y1=self.rect
                    return [types.SimpleNamespace(x=x,y=y) for _ in (0,1)
                            for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
            barrier_actors=[Barrier(ident,rect) for ident,rect in zip((31,32),
                scene["context"]["closed_divider_bounds_xy_m"])]
            modules={"carla":carla,"pipeline_capture":pipeline,"worker_exchange":exchange,
                     "worker_exchange.native_output":native_output,
                     "worker_exchange.world_restore":restore}
            with patch.dict(sys.modules,modules), \
                 patch.object(native_capture,"reviewed_context",side_effect=review), \
                 patch.object(native_capture,"spawn_divider",return_value=barrier_actors), \
                 patch.object(native_capture,"spawn_vehicle",return_value=actor), \
                 patch.object(native_capture,"CameraBank",Cameras):
                native_capture.run_native(scene,root,"localhost",2000)
            body=[json.loads(line) for line in (root/"ego-body-history.jsonl").read_text().splitlines()]
            control=[json.loads(line) for line in (root/"controller-history.jsonl").read_text().splitlines()]
            self.assertEqual([r["frame"] for r in body],list(range(1,7)))
            self.assertEqual([r["time_s"] for r in body],[r["time_s"] for r in control])
            self.assertEqual(len(seals),1)
            self.assertEqual(seals[0]["frames"],6)
            acquisition=json.loads((root/"acquisition.json").read_text())
            self.assertEqual(acquisition["ego-body-history.jsonl"]["sha256"],
                             native_capture.sha(root/"ego-body-history.jsonl"))
            self.assertEqual(len(json.loads((root/"divider-geometry.json").read_text())["actors"]),2)


if __name__=="__main__": unittest.main()
