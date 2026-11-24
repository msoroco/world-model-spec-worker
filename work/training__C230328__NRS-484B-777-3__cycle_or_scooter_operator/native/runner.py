"""Survey-gated two-rider Native roadway capture; CPU --check avoids CARLA import."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

AID='training__C230328__NRS-484B-777-3__cycle_or_scooter_operator'
CASE=AID+'__controlled_1'
CAMERAS=('overview','side','rear','subject')
COUNT=600
RATE=20


def config_check():
    cfg=json.loads((Path(__file__).resolve().parent/'config.json').read_text())
    if (cfg.get('assignment_id')!=AID or cfg.get('case_id')!=CASE or cfg.get('selected_case_id')!=CASE
            or cfg.get('candidate_id')!='primary' or cfg.get('law_id')!='NRS-484B-777-3'
            or cfg.get('cell_id')!='C230328' or cfg.get('actor')!='cycle_or_scooter_operator'
            or cfg.get('frames')!=COUNT or cfg.get('rate_hz')!=RATE or cfg.get('duration_s')!=30
            or [c.get('name') for c in cfg.get('cameras',[])]!=list(CAMERAS)
            or cfg.get('physical_acceptance_claimed') is not False):
        raise ValueError('Selected exact Native contract differs')
    return cfg


def survey_check(s):
    for key in ('map_name','map_source','public_dedication_source','public_vehicle_access_source',
                'roadway_boundary_source','shoulder_boundary_source','exclusive_use_source',
                'rider_device_source','bicycle_wheel_source','bicycle_diameter_source',
                'bicycle_moped_exclusion_source'):
        if not s.get(key):
            raise ValueError('Missing reviewed Native source: '+key)
    if s.get('exclusive_use_reviewed') is not True:
        raise ValueError('Exclusive-use exception not reviewed')
    riders=s.get('riders')
    if not isinstance(riders,list) or len(riders)!=2 or {r.get('rider_id') for r in riders}!=set((1,2)):
        raise ValueError('Selected source needs two distinct riders')
    for r in riders:
        if r.get('device_subtype')!='bicycle' or not r.get('device_blueprint') or not r.get('rider_blueprint'):
            raise ValueError('Qualifying bicycle identities required')
        if len(r.get('spawn_xyz_m',[]))!=3 or len(r.get('attach_xyz_m',[]))!=3:
            raise ValueError('Reviewed bicycle/rider transform missing')
        if not 0<r.get('target_speed_mps',0)<10:
            raise ValueError('Invalid rider travel speed')
        if r.get('roadway_occupied') is not True or r.get('shoulder_occupied') is not False or r.get('exclusive_use_occupied') is not False:
            raise ValueError('Roadway, shoulder, exclusive-use occupancy unreviewed')
    if set(s.get('camera_world_transforms',{}))!=set(CAMERAS):
        raise ValueError('Four reviewed camera transforms required')
    return s


def transform(carla,xyz,rotation):
    return carla.Transform(carla.Location(x=xyz[0],y=xyz[1],z=xyz[2]),
                           carla.Rotation(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))


def execute(output,survey,host,port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot,restore
    config_check();survey_check(survey)
    output=Path(output).resolve()
    if any((output/name).exists() for name in ('video_frames.jsonl','rider_poses.jsonl')):
        raise ValueError('Original frame sources already exist')
    client=carla.Client(host,port);client.set_timeout(120)
    saved=snapshot(client);world=client.get_world()
    if world.get_map().name!=survey['map_name']:
        raise ValueError('Live Native map differs from reviewed map')
    if saved['settings'].synchronous_mode:
        raise RuntimeError('Exclusive asynchronous Native world required')
    owned=[];encoders={};queues={}
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/RATE
        world.apply_settings(settings)
        lib=world.get_blueprint_library()
        pairs=[]
        for r in survey['riders']:
            dev=world.try_spawn_actor(lib.find(r['device_blueprint']),
                transform(carla,r['spawn_xyz_m'],[0,r.get('spawn_yaw_deg',0),0]))
            if dev is None:raise RuntimeError('Reviewed bicycle spawn failed')
            owned.append(dev)
            rider=world.try_spawn_actor(lib.find(r['rider_blueprint']),
                transform(carla,r['attach_xyz_m'],[0,0,0]),attach_to=dev)
            if rider is None:raise RuntimeError('Reviewed rider spawn failed')
            owned.append(rider);pairs.append((r,dev,rider))
        output.mkdir(parents=True,exist_ok=True)
        for c in config_check()['cameras']:
            bp=lib.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x',str(c['width']))
            bp.set_attribute('image_size_y',str(c['height']))
            bp.set_attribute('sensor_tick',str(1/RATE))
            spec=survey['camera_world_transforms'][c['name']]
            cam=world.spawn_actor(bp,transform(carla,spec['xyz_m'],spec['rotation_deg']))
            owned.append(cam);q=queue.Queue();cam.listen(q.put);queues[c['name']]=q
            encoders[c['name']]=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f"{c['width']}x{c['height']}",
                '-r',str(RATE),'-i','-','-frames:v',str(COUNT),'-c:v','ffv1',
                str(output/(c['name']+'.mkv'))],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        first=None
        with FrameMap(output/'video_frames.jsonl') as fmap,(output/'rider_poses.jsonl').open('x') as poses:
            for i in range(COUNT):
                for spec,dev,_ in pairs:
                    dev.set_target_velocity(carla.Vector3D(x=spec['target_speed_mps'],y=0,z=0))
                native=world.tick();snap=world.get_snapshot()
                if snap.frame!=native:raise RuntimeError('Original Native frame differs')
                if first is None:first=snap.timestamp.elapsed_seconds
                t=snap.timestamp.elapsed_seconds-first
                mapped={}
                for name,q in queues.items():
                    image=q.get(timeout=30)
                    if image.frame!=native:raise RuntimeError('Original camera frame differs')
                    encoders[name].stdin.write(image.raw_data);mapped[name]=image.frame
                fmap.append(native,t,camera_native_frames=mapped)
                riders=[]
                for spec,dev,rider in pairs:
                    pose=dev.get_transform();vel=dev.get_velocity();extent=dev.bounding_box.extent
                    riders.append({'rider_id':spec['rider_id'],'native_device_actor_id':dev.id,
                        'native_rider_actor_id':rider.id,'longitudinal_m':pose.location.x,
                        'lateral_m':pose.location.y,'half_length_m':extent.x,
                        'speed_mps':math.sqrt(vel.x*vel.x+vel.y*vel.y+vel.z*vel.z),
                        'roadway_occupied':spec['roadway_occupied'],
                        'shoulder_occupied':spec['shoulder_occupied'],
                        'exclusive_use_occupied':spec['exclusive_use_occupied']})
                poses.write(json.dumps({'video_frame':i,'native_frame':native,
                    'source_kind':'original_native_pose','riders':riders})+'\n')
        for name,proc in encoders.items():
            proc.stdin.close();err=proc.stderr.read()
            if proc.wait(timeout=180):raise RuntimeError('Camera encoding failed: '+name+' '+err.decode()[-300:])
        (output/'road_context.template.json').write_text(json.dumps({'assignment_id':AID,
            'review_kind':'original_source_review','rider_ids':[1,2],
            'device_subtypes':{'1':'bicycle','2':'bicycle'},'review_required':True},indent=2)+'\n')
        return {'case_id':CASE,'original_frames':COUNT,'physical_acceptance_claimed':False}
    finally:
        for proc in encoders.values():
            if proc.poll() is None:proc.kill();proc.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        restore(client,saved)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--survey',type=Path);parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000)
    a=parser.parse_args();config_check()
    if a.check:print(json.dumps({'passed':True,'case_id':CASE,'frames':COUNT,'cameras':list(CAMERAS),'native_imported':False,'physical_acceptance_claimed':False}))
    else:
        if a.survey is None or a.output_dir is None:parser.error('--survey and --output-dir required')
        print(json.dumps(execute(a.output_dir,json.loads(a.survey.read_text()),a.host,a.port)))
