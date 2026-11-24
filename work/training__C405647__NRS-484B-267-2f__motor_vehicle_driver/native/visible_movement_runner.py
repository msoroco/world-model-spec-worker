"""Vehicle-movement preparation variant. CPU --check never starts CARLA."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

AID='training__C405647__NRS-484B-267-2f__motor_vehicle_driver'
CAMERAS=('overview','approach','reference_corner','driver_reference')
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
        c.get('case_suffix') != 'visible_movement' or c.get('candidate_id') not in ('primary','fallback1','fallback2') or
        type(c.get('requested_preparation_movement_mps')) not in (int,float) or
        not 0.2 <= c['requested_preparation_movement_mps'] <= 1.0 or
        (c.get('law_id'),c.get('cell_id'),c.get('actor'))!=('NRS-484B-267-2f','C405647','motor_vehicle_driver') or
        (c.get('rate_hz'),c.get('duration_s'),c.get('frames'))!=(20,30,600) or
        [x.get('name') for x in c.get('cameras',[])]!=list(CAMERAS) or
        [(x.get('width'),x.get('height')) for x in c['cameras']]!=[(1920,1080),(1280,720),(1280,720),(1280,720)] or
        any(not x.get('pose_strategy') or not x.get('fov_deg') for x in c['cameras']) or
        c.get('physical_acceptance_claimed') is not False):
        raise ValueError('Exact two-phase emergency construction differs')
    return c


def survey_check(s,c=None):
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
    if c is not None and (abs(a[1]-c['requested_ego_lane_center_y_m'])>0.01 or
                          abs(b[0]-c['requested_emergency_spawn_x_m'])>0.01):
        raise ValueError('Reviewed candidate spawn differs from construction')
    if set(s['camera_world_transforms'])!=set(CAMERAS):raise ValueError('Four reviewed cameras missing')
    return s


def transform(carla,xyz,rotation):
    return carla.Transform(carla.Location(x=xyz[0],y=xyz[1],z=xyz[2]),
                           carla.Rotation(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))


def validate_native_lanes(ego_lane, emergency_lane):
    """Confirm authored opposite-direction lane placement from Native readback."""
    if ego_lane is None or emergency_lane is None:
        raise ValueError('Native driving lane readback missing')
    if (ego_lane.road_id != 405647 or emergency_lane.road_id != 405647 or
            ego_lane.lane_id != -1 or emergency_lane.lane_id != 1):
        raise ValueError('Native opposing routes differ from authored lanes')
    return {'road_id': 405647, 'ego_lane_id': -1,
            'emergency_lane_id': 1}


def subject_response(frame, config, ego_x, ego_y, emergency_x, ego_half_length=2.0,
                     emergency_half_length=2.0):
    """Request a right-edge stop until the approaching vehicle has passed.

    The stop and pass condition are engineering controls. Original poses and
    video must establish what actually happened before any physical conclusion.
    """
    if frame < 100:
        return (config['requested_initial_subject_speed_mps'], 0.0, 'initial_approach')
    if config['case_suffix'] == 'controlled_2':
        return (config['requested_subsequent_subject_speed_mps'], 0.0, 'continued_travel')
    if 100 <= frame < 120:
        remaining_s=(120-frame)/RATE
        lateral_velocity=(config['requested_right_edge_center_y_m']-ego_y)/remaining_s
        return (1.0, max(-1.0,min(0.0,lateral_velocity)), 'move_to_right_edge')
    passed = emergency_x + emergency_half_length < ego_x - ego_half_length
    if not passed:
        return (0.0, 0.0, 'stopped_until_passed')
    return (1.0, 0.0, 'resumed_after_pass')


def source_motion_request(frame, config):
    """Request visible vehicle movement before the full approach begins."""
    if frame < 80:
        return 0.0
    if frame < 100:
        return -config['requested_preparation_movement_mps']
    return -config['requested_subsequent_emergency_speed_mps']


def execute(output,survey,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore
    c=config();survey_check(survey,c);output=Path(output).resolve()
    if any((output/name).exists() for name in ('video_frames.jsonl','vehicle_poses.jsonl')):
        raise ValueError('Original Native frame sources already exist')
    client=carla.Client(host,port);client.set_timeout(120)
    saved=snapshot(client);world=client.get_world()
    if saved['settings'].synchronous_mode:raise RuntimeError('Exclusive asynchronous world required')
    actors=[];encoders={};queues={};capture_writer=None;restored=None;encoder_codes={}
    try:
        # The authored road is loaded only after the reviewed map/road identity is confirmed.
        if survey['map_name']!='C405647-two-phase-emergency' or survey['road_geometry_source']!='authored:runner.road_xml':
            raise ValueError('Authored OpenDRIVE identity differs')
        world=client.generate_opendrive_world(road_xml())
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/RATE
        world.apply_settings(settings)
        mapping=world.get_map()
        lane_readback=validate_native_lanes(
            mapping.get_waypoint(transform(carla,survey['ego_spawn_xyz_m'],[0,0,0]).location,
                                 project_to_road=False,lane_type=carla.LaneType.Driving),
            mapping.get_waypoint(transform(carla,survey['emergency_spawn_xyz_m'],[0,180,0]).location,
                                 project_to_road=False,lane_type=carla.LaneType.Driving))
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
        capture_writer=PipelineCapture(client,ego,output,c['case_id'],
                                       required_observations=c['required_atoms'])
        first=None
        with FrameMap(output/'video_frames.jsonl') as fmap,(output/'vehicle_poses.jsonl').open('x') as trace:
            for i in range(COUNT):
                # Source vehicle first moves at frame 80; visibility needs original pixel review.
                emergency.set_light_state(carla.VehicleLightState(special if (i//10)%2==0 else 0))
                emergency.set_target_velocity(carla.Vector3D(x=source_motion_request(i,c),y=0,z=0))
                ego_pose=ego.get_transform(); emergency_pose=emergency.get_transform()
                ego_extent=ego.bounding_box.extent.x; emergency_extent=emergency.bounding_box.extent.x
                ego_vx,ego_vy,phase=subject_response(
                    i,c,ego_pose.location.x,ego_pose.location.y,emergency_pose.location.x,
                    ego_extent,emergency_extent)
                ego.set_target_velocity(carla.Vector3D(x=ego_vx,y=ego_vy,z=0))
                native=world.tick();snap=world.get_snapshot()
                if snap.frame!=native:raise RuntimeError('Original Native frame mismatch')
                if first is None:first=snap.timestamp.elapsed_seconds
                capture_writer.capture(native,snap.timestamp.elapsed_seconds-first,
                                       extra={'emergency_actor_id':emergency.id})
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
                records[0]['requested_response_phase']=phase
                trace.write(json.dumps({'video_frame':i,'native_frame':native,'source_kind':'original_native_pose',
                                        'ego':records[0],'emergency':records[1]})+'\n')
        for name,p in encoders.items():
            p.stdin.close();err=p.stderr.read()
            encoder_codes[name]=p.wait(timeout=180)
            if encoder_codes[name]:raise RuntimeError('Camera encode failed: '+name+' '+err.decode()[-300:])
        capture_writer.close(confirmed=True)
        (output/'emergency_context.template.json').write_text(json.dumps({'assignment_id':AID,
            'ego_actor_id':ego.id,'emergency_actor_id':emergency.id,
            'requested_preparation_movement_frames': [80,99],
            'visible_preparation_original_review_required': True,
            'camera_sha256':{name+'.mkv':hashlib.sha256((output/(name+'.mkv')).read_bytes()).hexdigest()
                             for name in CAMERAS},
            'native_lane_readback':lane_readback,
            'independent_source_review_required':True},indent=2)+'\n')
    finally:
        if capture_writer is not None and not capture_writer.closed:
            capture_writer.close(confirmed=False)
        for p in encoders.values():
            if p.poll() is None:p.kill();p.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        restored=restore(client,saved)
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'native','diagnostic_fixture':False,
        'native_executed':True},indent=2)+'\n')
    seal_capture(output,frames=COUNT,restoration=restored,errors=[],
                 encoder_exit_codes=encoder_codes,context={'native_lane_readback':lane_readback})
    return {'case_id':c['case_id'],'original_frames':COUNT,
            'capture_sealed':True,'physical_acceptance_claimed':False}

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
