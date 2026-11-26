"""Prospective original Native acquisition for the exact green-arrow lane pair.

The runner refuses a generic traffic light. CARLA asset availability and visible
arrow pixels remain unverified until an original local attempt is audited.
"""
import hashlib
import json
from pathlib import Path
import queue
import subprocess

from draft_runner import request, source_row
from signal_source import map_inventory, observed_state

FRAMES=600
RATE=20
CAMERAS=(('overview',85,-17,16),('approach',45,-12,8),
         ('reference_corner',61,-8,7),('driver_reference',20,-1.75,3))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path,value):
    Path(path).write_text(json.dumps(value,indent=2)+'\n')


def check(config, road):
    if config.get('rate_hz')!=RATE or config.get('duration_s')!=30:
        raise ValueError('Exact 600-frame capture plan differs')
    expected=('overview','approach','reference_corner','driver_reference')
    if tuple(c.get('name') for c in config.get('cameras',[]))!=expected:
        raise ValueError('Exact four-camera plan differs')
    inventory=map_inventory(road)
    if inventory['lane_id']!=-1:
        raise ValueError('Original green-arrow lane differs')
    route_end_x=10+2.5*30
    if route_end_x>=120 or not 10<inventory['mount_m'][0]<route_end_x:
        raise ValueError('Authored vehicle route misses the overhead signal or road end')
    return {'frames':FRAMES,'rate_hz':RATE,'cameras':list(expected),
            'authored_start_x_m':10,'authored_end_x_m':route_end_x,
            'native_capture_implemented':True,'native_capture_executed':False,
            'official_authority_review_pending':True,'pixels_unverified':True,
            'physical_acceptance_claimed':False}


def execute(case_id, output_dir, host='127.0.0.1', port=2000):
    import carla
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    root=Path(__file__).resolve().parent
    road=(root/'road.xodr').read_text()
    output=Path(output_dir).resolve()
    if output.exists() and not (output/'candidate-selection.json').is_file():
        raise ValueError('Use a materialized Native attempt directory')
    config=json.loads((output/'config.json').read_text())
    if config['case_id']!=case_id:
        raise ValueError('Exact case identity differs')
    check(config,road)
    plan=request(0,case_id)
    client=carla.Client(host,port)
    client.set_timeout(180)
    saved=snapshot(client)
    initial=client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(('vehicle.','walker.','sensor.','controller.')) for a in initial.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned=[]
    encoders={}
    streams={}
    changed=False
    completed=False
    encoder_codes={}
    try:
        world=client.generate_opendrive_world(road,carla.OpendriveGenerationParameters(
            vertex_distance=.5,max_road_length=40,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings()
        settings.synchronous_mode=True
        settings.fixed_delta_seconds=1/RATE
        settings.substepping=True
        settings.max_substep_delta_time=.01
        settings.max_substeps=10
        world.apply_settings(settings)
        native_road=world.get_map().to_opendrive()
        inventory=map_inventory(native_road)
        exact_arrows=[a for a in world.get_actors() if getattr(a,'type_id',None)=='traffic.lane_control_signal'
                      and getattr(a,'attributes',{}).get('opendrive_signal_id')=='100']
        if len(exact_arrows)!=1:
            raise RuntimeError('Unique original downward-arrow lane-control actor unavailable')
        arrow=exact_arrows[0]
        observed_state(arrow,inventory)
        blueprints=world.get_blueprint_library()
        bp=blueprints.find('vehicle.tesla.model3')
        y=-1.75 if plan['target_lane_id']==-1 else -5.25
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(x=10,y=y,z=1)))
        if ego is None or ego.type_id!='vehicle.tesla.model3':
            raise RuntimeError('Native vehicle spawn failed')
        owned.append(ego)
        output.mkdir(parents=True,exist_ok=True)
        capture=output/'capture'
        graph_dir=capture/'native'/'graphs'/'base'
        graph_dir.mkdir(parents=True,exist_ok=True)
        (output/'native-map-readback.xodr').write_text(native_road)
        _write(output/'signal-inventory.json',inventory)
        for name,x,cy,z in CAMERAS:
            camera_bp=blueprints.find('sensor.camera.rgb')
            width,height=(1920,1080) if name=='overview' else (1280,720)
            camera_bp.set_attribute('image_size_x',str(width))
            camera_bp.set_attribute('image_size_y',str(height))
            camera_bp.set_attribute('fov','85')
            camera_bp.set_attribute('sensor_tick',str(1/RATE))
            camera=world.spawn_actor(camera_bp,carla.Transform(
                carla.Location(x=x,y=cy,z=z),carla.Rotation(pitch=-20)))
            owned.append(camera)
            stream=queue.Queue()
            camera.listen(stream.put)
            streams[name]=stream
            encoders[name]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}',
                '-r',str(RATE),'-i','-','-frames:v',str(FRAMES),
                '-c:v','ffv1','-level','1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        with FrameMap(output/'video_frames.jsonl') as frame_map, (output/'native-signal-rows.jsonl').open('x') as signal_rows, (output/'trace.jsonl').open('x') as trace, (capture/'evidence.jsonl').open('x') as evidence, (capture/'native'/'frames.jsonl').open('x') as graph_index:
            first_time=None
            for index in range(FRAMES):
                ego.set_target_velocity(carla.Vector3D(x=2.5,y=0,z=0))
                native_frame=world.tick()
                snap=world.get_snapshot()
                if snap.frame!=native_frame:
                    raise RuntimeError('Native tick identity differs')
                if first_time is None:
                    first_time=snap.timestamp.elapsed_seconds
                time_s=snap.timestamp.elapsed_seconds-first_time
                camera_frames={}
                camera_hashes={}
                for name,_,_,_ in CAMERAS:
                    image=streams[name].get(timeout=30)
                    while image.frame<native_frame:
                        image=streams[name].get(timeout=30)
                    if image.frame!=native_frame:
                        raise RuntimeError('Original camera frame mismatch: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name]=image.frame
                    camera_hashes[name]=hashlib.sha256(image.raw_data).hexdigest()
                frame_map.append(native_frame,time_s,camera_native_frames=camera_frames,source_rgb_sha256=camera_hashes)
                pose=ego.get_transform()
                waypoint=world.get_map().get_waypoint(pose.location,project_to_road=True,lane_type=carla.LaneType.Driving)
                if waypoint is None or waypoint.road_id!=1:
                    raise RuntimeError('Original actor road/lane readback absent')
                indication=observed_state(arrow,inventory)
                row=source_row(index,native_frame,time_s,ego,indication,inventory,waypoint,plan['target_lane_id'])
                signal_rows.write(json.dumps(row)+'\n')
                velocity=ego.get_velocity()
                speed=(velocity.x**2+velocity.y**2+velocity.z**2)**.5
                trace.write(json.dumps({'frame':native_frame,'time_s':time_s,
                    'position':{'x':pose.location.x,'y':pose.location.y,'z':pose.location.z},
                    'position_m':[pose.location.x,pose.location.y,pose.location.z],
                    'heading_deg':pose.rotation.yaw,'speed_mps':speed,
                    'speed_mph':speed/.44704,'velocity_mps':[velocity.x,velocity.y,velocity.z],
                    'control':{'throttle':0,'steer':0,'brake':0,'hand_brake':False}})+'\n')
                evidence.write(json.dumps({'original_frame':native_frame,'replay_frame':native_frame,
                    'recording_time_s':time_s,'replay_simulation_time_s':time_s,
                    'actor_id':ego.id,'ego':{'position_m':[pose.location.x,pose.location.y,pose.location.z],
                    'heading_deg':pose.rotation.yaw,'speed_mps':speed,
                    'body_vertices_m':row['vehicle']['body_vertices_m']},
                    'world':{'road_projection':{'road_id':waypoint.road_id,'lane_id':waypoint.lane_id,
                    's_m':waypoint.s}}})+'\n')
                graph=f'graphs/base/{native_frame:08d}.adapter.json'
                (graph_dir/f'{native_frame:08d}.adapter.json').write_text(json.dumps(
                    {'attributes':{'frame':native_frame},'nodes':[],'edges':[]})+'\n')
                graph_index.write(json.dumps({'abstract':graph,'adapter_graph':graph,
                    'base':graph,'edges':0,'frame':native_frame,'nodes':0,
                    'simulation_time':time_s,'time_s':time_s})+'\n')
        for name,process in encoders.items():
            process.stdin.close()
            error=process.stderr.read()
            encoder_codes[name]=process.wait(timeout=180)
            if encoder_codes[name] or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed '+name+': '+error.decode()[-400:])
        _write(capture/'manifest.json',{'frames':FRAMES,'extraction_confirmed':True,
            'synthetic_diagnostic':False,'sources':{'native-map-readback.xodr':_sha(output/'native-map-readback.xodr'),
            'trace.jsonl':_sha(output/'trace.jsonl')},'required_observations':[]})
        (capture/'recorder_info.txt').write_text('Original Native lane-control attempt; independent pixel and authority review pending.\n')
        completed=True
        return {'case_id':case_id,'frames':FRAMES,'native_sources_written':True,
                'physical_acceptance_claimed':False}
    except Exception as exc:
        if output.exists():
            _write(output/'native-run-status.json',{'errors':[str(exc)],'native_capture_completed':False})
        raise
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'): actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restoration=restore(client,saved)
            if completed:
                _write(output/'native-capture-report.json',{'case_id':case_id,
                    'frames':FRAMES,'encoder_exit_codes':encoder_codes,
                    'restoration':restoration,'physical_acceptance_claimed':False})
                _write(output/'acquisition-provenance.json',{'provenance_kind':'native',
                    'diagnostic_fixture':False})
                seal_capture(output,frames=FRAMES,restoration=restoration,errors=[],
                    encoder_exit_codes=encoder_codes,
                    context={'case_id':case_id,'law_id':'NRS-484B-307-12a'})
