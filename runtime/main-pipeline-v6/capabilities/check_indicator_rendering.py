#!/usr/bin/env python3
"""Render a stationary asset capability check; this is not a scenario baseline."""
import argparse
import json
from pathlib import Path
import queue
import carla
import numpy as np
from PIL import Image


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    client=carla.Client('127.0.0.1',args.port);client.set_timeout(30)
    world=client.get_world();old=world.get_settings();owned=[];observations=[]
    try:
        if old.synchronous_mode:raise ValueError('Capability check requires idle endpoint')
        s=world.get_settings();s.synchronous_mode=True;s.fixed_delta_seconds=.05;s.no_rendering_mode=False;world.apply_settings(s)
        bp=world.get_blueprint_library().find('vehicle.tesla.model3')
        if not world.get_map().get_spawn_points():raise ValueError('Native map spawn required for asset check')
        ego=world.spawn_actor(bp,world.get_map().get_spawn_points()[0]);owned.append(ego);ego.apply_control(carla.VehicleControl(brake=1))
        bp=world.get_blueprint_library().find('sensor.camera.rgb')
        for k,v in [('image_size_x','960'),('image_size_y','540'),('fov','80'),('sensor_tick','0')]:bp.set_attribute(k,v)
        camera=world.spawn_actor(bp,carla.Transform(carla.Location(x=-7,z=3.2),carla.Rotation(pitch=-15)),attach_to=ego,attachment_type=carla.AttachmentType.Rigid);owned.append(camera);q=queue.Queue();camera.listen(q.put)
        for i in range(160):
            enabled=40<=i<120;ego.set_light_state(carla.VehicleLightState.LeftBlinker if enabled else carla.VehicleLightState.NONE)
            frame=world.tick()
            image=q.get(timeout=30)
            while image.frame<frame:image=q.get(timeout=30)
            if image.frame!=frame:raise ValueError('Camera frame gap')
            pixels=np.frombuffer(image.raw_data,dtype=np.uint8).reshape((540,960,4))[:,:,:3][:,:,::-1]
            Image.fromarray(pixels.copy()).save(args.output/('%04d.png'%i))
            observations.append({'frame':frame,'time_s':(i+1)*.05,'api_bits':int(ego.get_light_state()),'image':'%04d.png'%i})
        (args.output/'observations.json').write_text(json.dumps({'blueprint':ego.type_id,'scope':'stationary lamp/camera capability, no law evaluation or baseline scenario','camera':{'position_m':[-7,0,3.2],'pitch_deg':-15,'width':960,'height':540,'fov_deg':80},'observations':observations},indent=2))
    finally:
        for actor in reversed(owned):
            if actor.type_id.startswith('sensor.'):actor.stop()
            actor.destroy()
        world.apply_settings(old)


if __name__=='__main__':main()
