"""Original selected C329654 delivery attempt; physical evidence, no legal verdict.

One native episode records all motion, queried controls/lights, original cameras
and PipelineCapture graphs. No replay is performed for conversion or validation.
"""
import argparse,json,math,queue,subprocess,sys,traceback,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent


def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def state(actor):
    from original_observations import actor_state
    value=actor_state(actor);value['body_vertices_native_m']=value['body_vertices_m']
    pose=actor.get_transform();box=actor.bounding_box;control=actor.get_control()
    value.update(yaw_rad=math.radians(pose.rotation.yaw),light_state_native=int(actor.get_light_state()),body_local_vertices_m=[[v.x,v.y,v.z] for v in box.get_local_vertices()],native_box_extent_m=[box.extent.x,box.extent.y,box.extent.z],pose_native_matrix=pose.get_matrix(),applied_control={k:getattr(control,k) for k in ['throttle','brake','steer','hand_brake','reverse','manual_gear_shift','gear']})
    return value


def check():
    import carla,numpy,PIL.Image,shapely.geometry,pipeline_capture,cleanup
    from build_left253_construction_v1 import check as geometry
    from left253_controller_v1 import InteractionController
    return dict(geometry(),motion_capability_established=False,worker_imports_passed=True)


def run(args):
    import carla,numpy as np
    from PIL import Image
    from shapely.geometry import MultiPoint,box
    from build_left253_construction_v1 import xodr,routes,surface
    from left253_controller_v1 import InteractionController
    from pipeline_capture import PipelineCapture
    from cleanup import restore
    from left253_delivery_values_v1 import finish as finish_delivery
    check();cfg=json.loads((ROOT/'config.json').read_text());out=Path(args.output);out.mkdir(parents=True,exist_ok=True);assert (out/'runner.py').read_bytes()==Path(__file__).read_bytes();assert json.loads((out/'config.json').read_text())==cfg
    client=carla.Client('127.0.0.1',22100);client.set_timeout(180)
    owned=[];actors={};encoders={};logs={};cameras={};queues={};capture=None;reader=None;rows=[];contacts=[];error=None;changed=False;restoration=None;inventory=None;channels={};distance_rows=[];distance=0.;previous_ego=None;complete=False
    try:
        world=client.get_world();previous=world.get_settings();weather=world.get_weather()
        assert not previous.synchronous_mode and not previous.no_rendering_mode
        assert not [a for a in world.get_actors() if a.type_id.startswith(('vehicle.','walker.','sensor.','controller.'))]
        prior_xml=world.get_map().to_opendrive();prior_name=world.get_map().name
        prior_path=next(p for p in client.get_available_maps() if p.rsplit('/',1)[-1]==prior_name.rsplit('/',1)[-1])
        (out/'previous-world.xodr').write_text(prior_xml)
        write(out/'previous-state.json',{'map':prior_name,'settings':str(previous),'settings_fields':{k:getattr(previous,k) for k in dir(previous) if not k.startswith('_') and isinstance(getattr(previous,k),(bool,int,float,type(None)))},'weather':str(weather),'weather_fields':{k:getattr(weather,k) for k in dir(weather) if not k.startswith('_') and isinstance(getattr(weather,k),(bool,int,float,type(None)))}})
        changed=True
        world=client.generate_opendrive_world(xodr(),carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        setting=world.get_settings();setting.synchronous_mode=True;setting.fixed_delta_seconds=.05;setting.substepping=True;setting.max_substep_delta_time=.01;setting.max_substeps=10;world.apply_settings(setting);world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map()
        specs=[('ego',-52.,1.75,0.),('initial_opposing',cfg['initial_center_x_m'],-1.75,180.)]+[('further_opposing_'+str(i+1),cfg['initial_center_x_m']+30.+18*i,-1.75,180.) for i in range(cfg['further_count'])]
        for role,x,y,yaw in specs:
            bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','left253_'+role)
            if bp.has_attribute('color'):bp.set_attribute('color','30,220,50' if role=='ego' else '220,50,40' if role=='initial_opposing' else '50,70,220')
            actor=world.spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=.5),carla.Rotation(yaw=yaw)));owned.append(actor);actors[role]=actor
            actor.apply_control(carla.VehicleControl(brake=1.,hand_brake=True))
        for _ in range(60):world.tick()
        initial_states={k:state(a) for k,a in actors.items()}
        for role,s in initial_states.items():assert s['speed_mps']<.05 and len(s['body_vertices_native_m'])==8
        roads=surface();region=box(-7,-7,7,7)
        def footprint(s):return MultiPoint([(v[0],v[1]) for v in s['body_vertices_native_m']]).convex_hull
        def authored_footprint(s):return MultiPoint([(v[0],-v[1]) for v in s['body_vertices_native_m']]).convex_hull
        assert all(roads.covers(authored_footprint(s)) for s in initial_states.values())
        metadata={};parameters={}
        for role,actor in actors.items():
            pc=actor.get_physics_control();wheels=pc.wheels;assert len(wheels)==4
            wheelbase=(max(w.position.x for w in wheels)-min(w.position.x for w in wheels))/100.
            parameters[role]={'max_steer_deg':max(w.max_steer_angle for w in wheels),'wheelbase_m':wheelbase}
            metadata[role]={'state':initial_states[role],'parameters':parameters[role],'physics':str(pc),'asset':actor.type_id,'operator':'Explicit authored ordinary physically controlling '+role+' driver','intent':'left turn' if role=='ego' else 'opposite-direction through route'}
            sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=actor);owned.append(sensor)
            sensor.listen(lambda e,r=role:contacts.append({'role':r,'frame':e.frame,'other_actor':e.other_actor.id}))
        write(out/'native-vehicle-metadata.json',metadata)
        authored=routes();paths={'ego':[(x,-y) for x,y in authored['ego']]}
        paths.update({role:[(s['position_m'][0]-i*.1,-1.75) for i in range(int((s['position_m'][0]+60)*10)+1)] for role,s in initial_states.items() if role!='ego'})
        controller=InteractionController(paths,parameters,cfg['opposing_request_mps'],cfg['duration_s'])
        camera_bp=world.get_blueprint_library().find('sensor.camera.rgb')
        for name,w,h,fov in [('overview',3840,2160,90),('signal',1280,720,65)]:
            for k,v in [('image_size_x',str(w)),('image_size_y',str(h)),('fov',str(fov)),('sensor_tick','0')]:camera_bp.set_attribute(k,v)
            if name=='overview':camera=world.spawn_actor(camera_bp,carla.Transform(carla.Location(x=40,y=-25,z=240),carla.Rotation(pitch=-90)))
            else:camera=world.spawn_actor(camera_bp,carla.Transform(carla.Location(x=-7,z=2.5),carla.Rotation(pitch=-12)),attach_to=actors['ego'])
            cameras[name]=camera;owned.append(camera);queues[name]=queue.Queue();camera.listen(queues[name].put)
            logs[name]=(out/(name+'.encoder.log')).open('x')
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s',str(w)+'x'+str(h),'-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1','-threads','2',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=logs[name])
        capture=PipelineCapture(client,actors['ego'],out,cfg['case_id'],visibility=True,required_observations=cfg.get('required_atoms',[]))
        from left253_native_inventory_v1 import NativeInventory
        inventory=NativeInventory(world,mapping,out)
        from left253_delivery_values_v1 import values as delivery_values
        reader=(out/'capture/evidence.jsonl').open()
        (out/'channels').mkdir()
        channels={c['name']:(out/'channels'/(c['name']+'.jsonl')).open('x') for c in cfg['recording_description']['channels']}
        write(out/'context.json',cfg['recorded_context'])
        start=world.get_snapshot().timestamp.elapsed_seconds
        signal_mask=int(carla.VehicleLightState.LeftBlinker);write(out/'signal-method.json',{'native_left_indicator_bit':signal_mask,'context':cfg['authored_context']['signal'],'device_approval':'External authored assumption, no simulator certification finding'})
        write(out/'authored_context_frozen.json',cfg['authored_test_context'])
        with (out/'native-motion.jsonl').open('x') as telemetry,(out/'video_frames.jsonl').open('x') as frames:
            for i in range(cfg['duration_s']*20):
                before={k:state(a) for k,a in actors.items()};frame_before=world.get_snapshot().frame;requested=controller.step(frame_before,i*.05,before)
                actors['ego'].set_light_state(carla.VehicleLightState.LeftBlinker)
                commands=[carla.command.ApplyVehicleControl(actors[role].id,carla.VehicleControl(throttle=r['throttle'],brake=r['brake'],steer=r['steer'],hand_brake=r['hand_brake'])) for role,r in requested.items()]
                assert not any(r.has_error() for r in client.apply_batch_sync(commands,False))
                frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start
                states={k:state(a) for k,a in actors.items()};occupancy={role:{'center_inside':region.contains(__import__('shapely.geometry',fromlist=['Point']).Point(*s['position_m'][:2])),'body_overlap':region.intersects(footprint(s)),'full_body_inside':region.contains(footprint(s)),'opposing_front_signed_distance_m':min(v[0] for v in s['body_vertices_native_m'])-7 if role!='ego' else None} for role,s in states.items()}
                row={'kind':'left253_native','frame':frame,'time_s':now,'states':states,'pre_control_frame':frame_before,'control_requests':requested,'occupancy':occupancy,'engineering_phase':controller.phase,'native_actor_inventory':[{'id':a.id,'type_id':a.type_id,'parent_id':None if a.parent is None else a.parent.id} for a in world.get_actors()],'contacts':list(contacts),'body_inside_authored_pavement':{role:roads.covers(authored_footprint(s)) for role,s in states.items()},'weather':str(world.get_weather()),'camera_metadata':{k:{'matrix':a.get_transform().get_matrix(),'inverse_matrix':a.get_transform().get_inverse_matrix(),'attributes':dict(a.attributes)} for k,a in cameras.items()}}
                row['governing_native_inventory']=inventory.capture(frame,now)
                capture.capture(frame,now,extra={'left253_native':row})
                event=json.loads(reader.readline());ego_position=states['ego']['position_m'][:2]
                if previous_ego is not None:distance+=math.dist(ego_position,previous_ego)
                distance_rows.append(distance);previous_ego=ego_position
                measured=delivery_values(row,event,distance)
                for name,file in channels.items():file.write(json.dumps({'time_s':now,'value':measured[name]},allow_nan=False)+'\n');file.flush()
                for name,w,h in [('overview',3840,2160),('signal',1280,720)]:
                    im=queues[name].get(timeout=30)
                    while im.frame<frame:im=queues[name].get(timeout=30)
                    assert im.frame==frame
                    rgb=np.frombuffer(im.raw_data,dtype=np.uint8).reshape(h,w,4)[:,:,:3][:,:,::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                    if i%100==0 or i==cfg['duration_s']*20-1:Image.fromarray(rgb).save(out/(name+'-%04d.png'%i))
                telemetry.write(json.dumps(row,allow_nan=False)+'\n');telemetry.flush();frames.write(json.dumps({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':now})+'\n');frames.flush();rows.append(row)
                if i%100==0:print(json.dumps({'frame_index':i,'phase':controller.phase,'ego':states['ego']['position_m'],'actual_speed_mps':states['ego']['speed_mps']}),flush=True)
                if contacts or not all(row['body_inside_authored_pavement'].values()):break
    except BaseException as exc:error={'error':str(exc),'traceback':traceback.format_exc()}
    finally:
        if inventory:inventory.close()
        if reader:reader.close()
        for file in channels.values():file.close()
        if capture:
            try:capture.close(confirmed=len(rows)==cfg['duration_s']*20 and error is None)
            except BaseException as exc:error=error or {'capture_close_error':str(exc)}
        for name,encoder in encoders.items():
            try:encoder.stdin.close();assert encoder.wait(timeout=180)==0
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            logs[name].close()
        if changed:
            try:restoration=restore(carla,client,world,owned,previous,weather,prior_path,prior_xml,'127.0.0.1',22100,out);write(out/'engine_scene_restored.json',restoration)
            except BaseException as exc:error=error or {'restoration_error':str(exc),'traceback':traceback.format_exc()}
        inside=next((r for r in rows if r['occupancy']['ego']['full_body_inside']),None)
        final=[r for r in rows if r['time_s']>cfg['duration_s']-3]
        report={'kind':'left253_native_physical_diagnostics','frames':len(rows),'expected_frames':cfg['duration_s']*20,'error':error,'contacts':contacts,'full_recording':len(rows)==cfg['duration_s']*20,'first_full_ego_inside':None if inside is None else {'frame':inside['frame'],'time_s':inside['time_s'],'opposing':inside['occupancy']['initial_opposing']},'phase_history':[] if not rows else controller.phase_history,'ego_turn_completed':any(r['engineering_phase']=='departure' for r in rows),'final_stopped_observation':len(final)>=59 and all(s['speed_mps']<.1 for r in final for s in r['states'].values()),'restored':bool(restoration and restoration['restored']),'delivery_accepted':False,'required_saved_audits':['Full original video decode and actual pixels','Signal continuity/path integration and course-change bracket','All participant approach/wait/braking/passage/outcome histories','Camera/graph/body/frame joins and body containment']}
        write(out/'native-physical-report.json',report)
        complete=finish_delivery(out,cfg,rows,report,error,distance_rows)
    return 0 if complete else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir',default=str(ROOT));p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=22100);a=p.parse_args()
    cfg=json.loads((ROOT/'config.json').read_text());assert cfg['cell_id']=='C329654' and cfg['actor']=='motor_vehicle_driver';assert cfg['maximum_frames']==cfg['duration_s']*20;assert a.host=='127.0.0.1' and a.port==22100
    if a.check:print(json.dumps(check()))
    else:a.output=a.output_dir;sys.exit(run(a))
