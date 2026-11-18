"""Mock Native runner lifecycle ordering; protocol proof, never a real capture."""
from __future__ import annotations
import argparse,copy,importlib.util,json,sys,tempfile,types
from pathlib import Path
folder=Path(__file__).resolve().parent

def run(case):
    entry=next((x for x in json.loads((folder/'execution-manifest.json').read_text())['cases'] if x['case_id']==case),None)
    if entry is None:raise ValueError('Unknown exact case')
    construction=json.loads((folder/entry['construction']).read_text());files={x['path']:x['content'] for x in construction['files']}
    events=[]
    class Settings:
        synchronous_mode=False;fixed_delta_seconds=.1
    class Waypoint:
        transform=object();road_id=1;lane_width=2.8
    class World:
        def __init__(self):self.settings=Settings();self.frame=0
        def get_settings(self):return copy.copy(self.settings)
        def apply_settings(self,value):
            self.settings=copy.copy(value)
            if not value.synchronous_mode:events.append('restoration_verified')
        def get_map(self):return types.SimpleNamespace(name='synthetic_narrow_road')
        def tick(self):self.frame+=1;return self.frame
        def get_snapshot(self):return types.SimpleNamespace(frame=self.frame,timestamp=types.SimpleNamespace(elapsed_seconds=self.frame*.05))
    world=World()
    class Actor:
        def __init__(self,number):self.id=number;self.control=types.SimpleNamespace(reverse=True)
        def apply_control(self,control):self.control=control
        def get_control(self):return self.control
        def get_transform(self):return types.SimpleNamespace(location=types.SimpleNamespace(x=20.0-self.id*.01,y=1.75,z=0))
        def get_velocity(self):return types.SimpleNamespace(x=0.,y=0.)
        bounding_box=types.SimpleNamespace(get_world_vertices=lambda transform:[types.SimpleNamespace(x=0.,y=0.,z=0.) for _ in range(8)])
        def destroy(self):events.append('actor_destroyed')
    carla=types.ModuleType('carla')
    carla.Client=lambda host,port:types.SimpleNamespace(set_timeout=lambda n:None,get_world=lambda:world)
    carla.VehicleControl=lambda **kw:types.SimpleNamespace(**kw)
    pipeline_mod=types.ModuleType('pipeline_capture')
    class PipelineCapture:
        def __init__(self,*args,**kwargs):pass
        def capture(self,frame,time):return {'frame':frame,'time_s':time}
        def close(self,confirmed):events.append('capture_finished')
    pipeline_mod.PipelineCapture=PipelineCapture
    native=types.ModuleType('worker_exchange.native_output')
    class FrameMap:
        def __init__(self,path):pass
        def append(self,frame,time):pass
        def close(self):pass
    native.FrameMap=FrameMap
    native.seal_capture=lambda *args,**kwargs:events.append('native_exit')
    camera_mod=types.ModuleType('backing_camera_capture');camera_mod.CAMERAS=('overview','approach','reference_corner','driver_reference')
    class Camera:
        def __init__(self,*args):pass
        def wait_for_frame(self,frame):pass
        def verify_frames(self,frames):pass
        def close(self):pass
    class Sink:
        def __init__(self,*args):pass
        def close(self):
            if 'encoders_closed' not in events:events.append('encoders_closed')
    camera_mod.FireCameraCapture=Camera;camera_mod.FFmpegSourceSink=Sink
    modules={'carla':carla,'pipeline_capture':pipeline_mod,'worker_exchange.native_output':native,'backing_camera_capture':camera_mod}
    original={key:sys.modules.get(key) for key in modules}
    try:
        sys.modules.update(modules)
        with tempfile.TemporaryDirectory(prefix='backing-lifecycle-') as raw:
            out=Path(raw);(out/'config.json').write_text(files['config.json'])
            source=out/'runner.py';source.write_text(files['runner.py'])
            spec=importlib.util.spec_from_file_location('backing_lifecycle_runner',source);runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
            runner.choose_narrow_road=lambda world_map:{'ego':Waypoint(),'other':Waypoint(),'front':Waypoint(),'lane_width_m':2.8}
            actors=iter((Actor(1),Actor(2)));runner._spawn=lambda *args:next(actors)
            runner.run(out,'127.0.0.1',2000)
        events.append('owner_released')
        saved_log=folder/('first-saved-proof.log' if entry==json.loads((folder/'execution-manifest.json').read_text())['cases'][0] else entry['post_capture']['test_log'])
        if not saved_log.is_file() or not json.loads(saved_log.read_text()).get('positive_saved_processing'):
            raise ValueError('Saved processing proof missing before release protocol')
        events.append('saved_processing_started')
    finally:
        for key,value in original.items():
            if value is None:sys.modules.pop(key,None)
            else:sys.modules[key]=value
    expected=['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started']
    filtered=[x for x in events if x in expected]
    if filtered!=expected:raise ValueError('Native ownership closure order changed: '+str(events))
    return {'case_id':case,'events':filtered,'fixture_only':True,'actual_native_capture':False,'saved_processing_proof_bound':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);a=p.parse_args();print(json.dumps(run(a.case),indent=2))
if __name__=='__main__':main()
