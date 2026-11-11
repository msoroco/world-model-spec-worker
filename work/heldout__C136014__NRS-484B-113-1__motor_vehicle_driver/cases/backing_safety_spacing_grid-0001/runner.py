"""Exact C136014 backing capture against an operator-owned CARLA world.

CPU --check validates the selected construction. Live motion and camera coverage
remain subject to original-source verification after an authorized capture.
"""
from __future__ import annotations
import argparse
import json
from math import hypot
from pathlib import Path

CASE_SUFFIX='__backing_safety_spacing_grid-0001'

def check_config(config):
    if (config.get('law_id'),config.get('cell_id'),config.get('actor')) != ('NRS-484B-113-1','C136014','motor_vehicle_driver'):
        raise ValueError('wrong law/cell/actor for backing exact case')
    if not config.get('selected_case_id','').endswith(CASE_SUFFIX):
        raise ValueError('wrong selected backing case')
    if config.get('rate_hz')!=20 or config.get('frames')!=160 or len(config.get('cameras',[]))!=4:
        raise ValueError('exact 20 Hz four-camera duration contract missing')
    if config.get('case',{}).get('case_id')!=config['selected_case_id']:
        raise ValueError('case/config identity differs')
    return True

def choose_narrow_road(world_map):
    """Select one connected travel lane with room for reverse encounter."""
    for spawn in world_map.get_spawn_points():
        waypoint=world_map.get_waypoint(spawn.location)
        if waypoint is None or waypoint.is_junction or not 2.3<=waypoint.lane_width<=3.0:
            continue
        behind=waypoint.previous(16.0)
        ahead=waypoint.next(18.0)
        if len(behind)!=1 or len(ahead)!=1:
            continue
        rear,front=behind[0],ahead[0]
        if any(w.is_junction or w.road_id!=waypoint.road_id or w.lane_id!=waypoint.lane_id for w in (rear,front)):
            continue
        return {'ego':waypoint,'other':rear,'front':front,'lane_width_m':waypoint.lane_width}
    raise ValueError('No connected Native narrow-road 16 m reverse encounter')

def _spawn(world,blueprint_id,transform):
    actor=world.try_spawn_actor(world.get_blueprint_library().find(blueprint_id),transform)
    if actor is None:raise ValueError('Native actor spawn failed: '+blueprint_id)
    return actor

def _state(actor):
    loc=actor.get_transform().location;vel=actor.get_velocity()
    return {'actor_id':actor.id,'position_m':[loc.x,loc.y,loc.z],
            'speed_mps':hypot(vel.x,vel.y),'body_vertices_m':[
                [p.x,p.y,p.z] for p in actor.bounding_box.get_world_vertices(actor.get_transform())]}

def run(output,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from backing_camera_capture import CAMERAS,FireCameraCapture,FFmpegSourceSink
    output=Path(output);config=json.loads((output/'config.json').read_text());check_config(config)
    client=carla.Client(host,port);client.set_timeout(30)
    world=client.get_world();original=world.get_settings();owned=[];sinks={};camera=None;pipeline=None;mapping=None;stream=None
    frames=[];failed=False;restored=False
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        route=choose_narrow_road(world.get_map())
        ego=_spawn(world,'vehicle.tesla.model3',route['ego'].transform);owned.append(ego)
        other=_spawn(world,'vehicle.audi.tt',route['other'].transform);owned.append(other)
        for name in CAMERAS:sinks[name]=FFmpegSourceSink(output,name)
        camera=FireCameraCapture(world,carla,ego,sinks)
        pipeline=PipelineCapture(client,ego,output,config['selected_case_id'],required_observations=config.get('required_atoms',[]))
        mapping=FrameMap(output/'video_frames.jsonl')
        stream=(output/'backing_history.jsonl').open('x',buffering=1)
        start=None
        for _ in range(config['frames']):
            ego.apply_control(carla.VehicleControl(throttle=.22,reverse=True,steer=0))
            other.apply_control(carla.VehicleControl(throttle=.16,steer=0))
            frame=world.tick();snapshot=world.get_snapshot()
            if snapshot.frame!=frame:raise ValueError('Native snapshot/frame mismatch')
            if start is None:start=snapshot.timestamp.elapsed_seconds
            time_s=snapshot.timestamp.elapsed_seconds-start
            camera.wait_for_frame(frame)
            row=pipeline.capture(frame,time_s)
            if row.get('frame')!=frame or row.get('time_s')!=time_s:raise ValueError('Pipeline frame join differs')
            mapping.append(frame,time_s)
            stream.write(json.dumps({'frame':frame,'time_s':time_s,'ego':_state(ego),'other':_state(other),
                                     'ego_reverse_gear':bool(ego.get_control().reverse),
                                     'road_id':route['ego'].road_id,'lane_width_m':route['lane_width_m']})+'\n')
            frames.append(frame)
        camera.verify_frames(frames)
    except BaseException:
        failed=True;raise
    finally:
        if stream:stream.close()
        if mapping:mapping.close()
        if pipeline:pipeline.close(confirmed=not failed)
        if camera:camera.close()
        for sink in sinks.values():sink.close()
        for actor in reversed(owned):actor.destroy()
        world.apply_settings(original)
        current=world.get_settings();restored=(current.synchronous_mode==original.synchronous_mode and current.fixed_delta_seconds==original.fixed_delta_seconds)
        if not restored:raise ValueError('Native settings restoration readback differs')
    if not frames:raise ValueError('No Native backing frames')
    (output/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'native','diagnostic_fixture':False,'original_frames':len(frames)})+'\n')
    seal_capture(output,frames=len(frames),restoration={'restored':restored},errors=[],
                 encoder_exit_codes={name:0 for name in CAMERAS},
                 context={'native_map_name':world.get_map().name,'road_id':route['ego'].road_id})

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000)
    a=p.parse_args()
    if a.check:
        check_config(json.loads(Path('config.json').read_text()))
        return
    if not a.output_dir:p.error('--output-dir required')
    run(a.output_dir,a.host,a.port)
if __name__=='__main__':main()
