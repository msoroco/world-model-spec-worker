"""CARLA-lazy original capture for C5191 marked approach and left turn."""
import argparse,json
from pathlib import Path
from lane_camera_capture import CAMERAS,LaneCameraCapture,LosslessSourceSink
from lane_construction import control_step
from turn_construction import CASES,select_marked_left_scene,targets
from turn_originals import TurnSourceRecorder

def check_config(config):
    case=config.get('selected_case_id','');suffix=next((s for s in CASES if case.endswith('__'+s)),None)
    if suffix is None or config.get('case',{}).get('case_id')!=case:raise ValueError('Unknown C5191 exact left-turn case')
    if (config.get('law_id'),config.get('cell_id'),config.get('actor'))!=('LVMC-11-18-030-B','C5191','motor_vehicle_driver'):
        raise ValueError('C5191 turn identity differs')
    if (config.get('rate_hz'),config.get('frames'),config.get('duration_s'))!=(20,160,8):
        raise ValueError('C5191 capture needs 160 frames at 20 Hz')
    if not isinstance(config.get('case',{}).get('recording_description'),dict):raise ValueError('Missing exact recording description')
    cameras=config.get('cameras',[])
    if [x.get('name') for x in cameras]!=list(CAMERAS):raise ValueError('Four named cameras required')
    for c in cameras:
        profile=CAMERAS[c['name']]
        if (c.get('width'),c.get('height'),c.get('fov_deg'))!=(*profile[2],profile[3]):
            raise ValueError('Source camera profile differs')
    e=config.get('engineering',{})
    if set(e)-{'route_spacing_m','approach_steps','route_candidate_index','target_speed_mps','speed_gain','crossing_fraction'}:
        raise ValueError('Unknown turn engineering knob')
    if (e.get('route_spacing_m',2.),e.get('approach_steps',12)) not in ((2.,12),(1.,24)):
        raise ValueError('Unsupported turn route sampling')
    if e.get('route_candidate_index',0) not in (0,1):raise ValueError('Unsupported turn candidate index')
    if (e.get('target_speed_mps',6.),e.get('speed_gain',.25)) not in ((6.,.25),(4.5,.2)):
        raise ValueError('Unsupported turn controller tuning')
    expected={'turn_excursion-0000':.2,'turn_excursion-0001':.6,'turn_excursion-0002':.4}.get(suffix,.6)
    if e.get('crossing_fraction',.6)!=expected:raise ValueError('Turn comparison crossing request differs')
    return suffix

def run(output_dir,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    output=Path(output_dir);config=json.loads((output/'config.json').read_text());suffix=check_config(config);engineering=config.get('engineering',{})
    client=carla.Client(host,port);client.set_timeout(30.);world=client.get_world();original=world.get_settings()
    ego=None;cameras=pipeline=recorder=frame_map=None;sinks={};frames=[];errors=[];restored=False;previous_lights=None
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        scene=select_marked_left_scene(world.get_map(),spacing_m=engineering.get('route_spacing_m',2.),approach_steps=engineering.get('approach_steps',12),candidate_index=engineering.get('route_candidate_index',0));plan=targets(scene,suffix,crossing_fraction=engineering.get('crossing_fraction',.6))
        blueprint=world.get_blueprint_library().find('vehicle.tesla.model3');ego=world.try_spawn_actor(blueprint,scene['approach'][0].transform)
        if ego is None:raise ValueError('C5191 Native ego spawn failed')
        previous_lights=ego.get_light_state() if hasattr(ego,'get_light_state') else None
        if hasattr(ego,'set_light_state'):
            ego.set_light_state(carla.VehicleLightState.LeftBlinker if plan['indicator_requested'] else carla.VehicleLightState.NONE)
        for name in CAMERAS:sinks[name]=LosslessSourceSink(output,name)
        cameras=LaneCameraCapture(world,carla,ego,sinks);pipeline=PipelineCapture(client,ego,output,config['selected_case_id'],required_observations=config.get('required_atoms',[]));recorder=TurnSourceRecorder(output,ego,scene);frame_map=FrameMap(output/'video_frames.jsonl')
        start=None
        for index in range(config['frames']):
            target=plan['targets_xy_m'][min(1+index//5,len(plan['targets_xy_m'])-1)]
            transform=ego.get_transform();location=transform.location;forward=transform.get_forward_vector();velocity=ego.get_velocity()
            command=control_step([location.x,location.y],[forward.x,forward.y],[velocity.x,velocity.y],target,target_speed_mps=engineering.get('target_speed_mps',6.),speed_gain=engineering.get('speed_gain',.25));ego.apply_control(carla.VehicleControl(**command))
            frame=world.tick();snapshot=world.get_snapshot()
            if snapshot.frame!=frame:raise ValueError('C5191 Native snapshot frame differs')
            if start is None:start=snapshot.timestamp.elapsed_seconds
            time_s=snapshot.timestamp.elapsed_seconds-start;cameras.wait_for_frame(frame)
            waypoint=world.get_map().get_waypoint(ego.get_location());pipeline.capture(frame,time_s);recorder.append(frame,time_s,waypoint);frame_map.append(frame,time_s);frames.append(frame)
        cameras.verify(frames)
    except BaseException as exc:errors.append(str(exc));raise
    finally:
        if frame_map is not None:frame_map.close()
        if recorder is not None:recorder.close()
        if pipeline is not None:pipeline.close(confirmed=not errors)
        if cameras is not None:cameras.close()
        for sink in sinks.values():sink.close()
        if ego is not None:
            if previous_lights is not None and hasattr(ego,'set_light_state'):ego.set_light_state(previous_lights)
            ego.destroy()
        world.apply_settings(original);restored=(world.get_settings().synchronous_mode==original.synchronous_mode and world.get_settings().fixed_delta_seconds==original.fixed_delta_seconds)
        if not restored:raise ValueError('C5191 Native world restoration differs')
    if errors or len(frames)!=config['frames']:raise ValueError('C5191 Native capture incomplete')
    (output/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'native','diagnostic_fixture':False,'original_frames':len(frames)})+'\n')
    seal_capture(output,frames=len(frames),restoration={'restored':restored},errors=[],encoder_exit_codes={name:0 for name in CAMERAS},context={'native_map_name':world.get_map().name,'approach_road_id':scene['approach_road_id'],'approach_lane_id':scene['approach_lane_id'],'left_exit_road_id':scene['exit_road_id']})
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--output-dir');parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
    if args.check:
        config=Path('config.json')
        if not config.is_file():raise ValueError('Materialized config required')
        check_config(json.loads(config.read_text()));return
    if not args.output_dir:parser.error('--output-dir required for Native capture')
    run(args.output_dir,args.host,args.port)
if __name__=='__main__':main()
