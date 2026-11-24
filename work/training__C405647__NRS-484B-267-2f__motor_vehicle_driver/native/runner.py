"""Two-phase emergency approach capture. CPU --check never starts CARLA."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

AID='training__C405647__NRS-484B-267-2f__motor_vehicle_driver'
CAMERAS=('overview','ego_front','emergency_side','rear')
RATE=20
COUNT=600


def road_xml():
    root=ET.Element('OpenDRIVE')
    ET.SubElement(root,'header',revMajor='1',revMinor='4',name='C405647-two-phase-emergency',version='1',north='10',south='-10',east='120',west='-120',vendor='worker')
    road=ET.SubElement(root,'road',id='405647',name='emergency_approach',length='240',junction='-1')
    ET.SubElement(road,'link')
    ET.SubElement(ET.SubElement(road,'planView'),'geometry',s='0',x='-120',y='0',hdg='0',length='240').append(ET.Element('line'))
    ET.SubElement(ET.SubElement(road,'elevationProfile'),'elevation',s='0',a='0',b='0',c='0',d='0')
    lanes=ET.SubElement(road,'lanes');ET.SubElement(lanes,'laneOffset',s='0',a='0',b='0',c='0',d='0')
    section=ET.SubElement(lanes,'laneSection',s='0')
    for side,index in (('left',1),('center',0),('right',-1)):
        lane=ET.SubElement(ET.SubElement(section,side),'lane',id=str(index),type='none' if index==0 else 'driving',level='false')
        if index:ET.SubElement(lane,'width',sOffset='0',a='3.5',b='0',c='0',d='0')
        ET.SubElement(lane,'roadMark',sOffset='0',type='solid' if index==0 else 'broken',color='yellow' if index==0 else 'white',width='0.12')
    ET.SubElement(road,'objects');ET.SubElement(road,'signals')
    return ET.tostring(root,encoding='unicode')


def config():
    c=json.loads((Path(__file__).resolve().parent/'config.json').read_text())
    if (c.get('assignment_id')!=AID or c.get('case_id')!=AID+'__'+c.get('case_suffix','') or
        c.get('case_suffix') not in ('controlled_1','controlled_2') or c.get('candidate_id')!='primary' or
        (c.get('law_id'),c.get('cell_id'),c.get('actor'))!=('NRS-484B-267-2f','C405647','motor_vehicle_driver') or
        (c.get('rate_hz'),c.get('duration_s'),c.get('frames'))!=(20,30,600) or
        [x.get('name') for x in c.get('cameras',[])]!=list(CAMERAS) or
        c.get('physical_acceptance_claimed') is not False):
        raise ValueError('Exact two-phase emergency construction differs')
    return c


def survey_check(s):
    for k in ('map_name','map_source','road_geometry_source','ego_blueprint','emergency_blueprint',
              'ego_spawn_xyz_m','emergency_spawn_xyz_m','camera_world_transforms',
              'emergency_authorization_source','qualifying_flash_equipment_source','officer_direction_review_source'):
        if not s.get(k):raise ValueError('Reviewed Native survey source missing: '+k)
    if s.get('emergency_vehicle_authorized') is not True or s.get('qualifying_flash_equipment_reviewed') is not True:
        raise ValueError('Emergency authorization or light equipment not reviewed')
    if type(s.get('officer_directed_otherwise')) is not bool:
        raise ValueError('Officer direction exception unreviewed')
    a,b=s['ego_spawn_xyz_m'],s['emergency_spawn_xyz_m']
    if len(a)!=3 or len(b)!=3 or not a[0]<b[0]-20 or not a[1]<-1 or not b[1]>1:
        raise ValueError('Two-direction approach geometry missing')
    if set(s['camera_world_transforms'])!=set(CAMERAS):raise ValueError('Four reviewed cameras missing')
    return s


def transform(carla,xyz,rotation):
    return carla.Transform(carla.Location(x=xyz[0],y=xyz[1],z=xyz[2]),
                           carla.Rotation(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))


def execute(output,survey,host,port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot,restore
    c=config();survey_check(survey);output=Path(output).resolve()
    if any((output/name).exists() for name in ('video_frames.jsonl','vehicle_poses.jsonl')):
        raise ValueError('Original Native frame sources already exist')
    client=carla.Client(host,port);client.set_timeout(120)
    saved=snapshot(client);world=client.get_world()
    if saved['settings'].synchronous_mode:raise RuntimeError('Exclusive asynchronous world required')
    actors=[];encoders={};queues={}
    try:
        # The authored road is loaded only after the reviewed map/road identity is confirmed.
        if survey['map_name']!='C405647-two-phase-emergency' or survey['road_geometry_source']!='authored:runner.road_xml':
            raise ValueError('Authored OpenDRIVE identity differs')
        world=client.generate_opendrive_world(road_xml())
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/RATE
        world.apply_settings(settings)
        lib=world.get_blueprint_library()
        ego=world.try_spawn_actor(lib.find(survey['ego_blueprint']),transform(carla,survey['ego_spawn_xyz_m'],[0,0,0]))
        emergency=world.try_spawn_actor(lib.find(survey['emergency_blueprint']),transform(carla,survey['emergency_spawn_xyz_m'],[0,180,0]))
        if ego is None or emergency is None:raise RuntimeError('Reviewed vehicle spawn failed')
        actors.extend((ego,emergency));output.mkdir(parents=True,exist_ok=True)
        special=carla.VehicleLightState.Special1
        for x in c['cameras']:
            bp=lib.find('sensor.camera.rgb');bp.set_attribute('image_size_x',str(x['width']))
            bp.set_attribute('image_size_y',str(x['height']));bp.set_attribute('sensor_tick',str(1/RATE))
            pose=survey['camera_world_transforms'][x['name']]
            cam=world.spawn_actor(bp,transform(carla,pose['xyz_m'],pose['rotation_deg']))
            actors.append(cam);q=queue.Queue();cam.listen(q.put);queues[x['name']]=q
            encoders[x['name']]=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f"{x['width']}x{x['height']}",
                '-r',str(RATE),'-i','-','-frames:v',str(COUNT),'-c:v','ffv1',
                str(output/(x['name']+'.mkv'))],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        first=None
        with FrameMap(output/'video_frames.jsonl') as fmap,(output/'vehicle_poses.jsonl').open('x') as trace:
            for i in range(COUNT):
                # First ego moves toward stationary emergency. Emergency moves toward ego after frame 100.
                emergency.set_light_state(carla.VehicleLightState(special if (i//10)%2==0 else 0))
                emergency.set_target_velocity(carla.Vector3D(x=-2 if i>=100 else 0,y=0,z=0))
                ego_target=1 if c['case_suffix']=='controlled_1' and i>=100 else 3
                ego.set_target_velocity(carla.Vector3D(x=ego_target,y=0,z=0))
                native=world.tick();snap=world.get_snapshot()
                if snap.frame!=native:raise RuntimeError('Original Native frame mismatch')
                if first is None:first=snap.timestamp.elapsed_seconds
                mapped={}
                for name,q in queues.items():
                    image=q.get(timeout=30)
                    if image.frame!=native:raise RuntimeError('Original camera frame mismatch')
                    encoders[name].stdin.write(image.raw_data);mapped[name]=image.frame
                fmap.append(native,snap.timestamp.elapsed_seconds-first,camera_native_frames=mapped)
                records=[]
                for actor in (ego,emergency):
                    p=actor.get_transform();v=actor.get_velocity();e=actor.bounding_box.extent
                    records.append({'actor_id':actor.id,'x_m':p.location.x,'y_m':p.location.y,
                        'heading_rad':p.rotation.yaw*math.pi/180,'velocity_x_mps':v.x,'velocity_y_mps':v.y,
                        'speed_mps':math.hypot(v.x,v.y),'half_length_m':e.x,'half_width_m':e.y})
                records[1]['special1_light_on']=bool(emergency.get_light_state() & special)
                trace.write(json.dumps({'video_frame':i,'native_frame':native,'source_kind':'original_native_pose',
                                        'ego':records[0],'emergency':records[1]})+'\n')
        for name,p in encoders.items():
            p.stdin.close();err=p.stderr.read()
            if p.wait(timeout=180):raise RuntimeError('Camera encode failed: '+name+' '+err.decode()[-300:])
        (output/'emergency_context.template.json').write_text(json.dumps({'assignment_id':AID,
            'ego_actor_id':ego.id,'emergency_actor_id':emergency.id,'camera_sha256':{},
            'independent_source_review_required':True},indent=2)+'\n')
        return {'case_id':c['case_id'],'original_frames':COUNT,'physical_acceptance_claimed':False}
    finally:
        for p in encoders.values():
            if p.poll() is None:p.kill();p.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        restore(client,saved)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true')
    ap.add_argument('--survey',type=Path);ap.add_argument('--output-dir',type=Path)
    ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=2000)
    a=ap.parse_args();c=config()
    if a.check:
        print(json.dumps({'passed':True,'case_id':c['case_id'],'frames':COUNT,'cameras':CAMERAS,
                          'native_imported':False,'physical_acceptance_claimed':False}))
    else:
        if a.survey is None or a.output_dir is None:ap.error('--survey and --output-dir required')
        print(json.dumps(execute(a.output_dir,json.loads(a.survey.read_text()),a.host,a.port)))
