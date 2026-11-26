"""C230266 sidewalk encounter capture; physical and legal review stays open."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from audio_source import LiveMicrophone

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check(config):
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C230266', 'LVMC-11-40-180-C', 'cycle_or_scooter_operator'):
        raise ValueError('Frozen assignment identity differs')
    if config['duration_s'] != 30 or config['rate_hz'] != 20:
        raise ValueError('30 second 20 Hz capture contract differs')
    if tuple(x['name'] for x in config['cameras']) != CAMERAS:
        raise ValueError('Four original source cameras required')
    if config['device_blueprint_filter'] != 'vehicle.diamondback.century':
        raise ValueError('Unreviewed replacement vehicle class')
    if config['pedestrian_microphone']['location'] != 'pedestrian_actor':
        raise ValueError('Audio must be measured at pedestrian location')
    if config['signal_frame'] is not None and not 0 <= config['signal_frame'] < 600:
        raise ValueError('Signal frame outside original capture')
    road = ET.parse(HERE/'road.xodr').getroot()
    sidewalk = road.find('.//lane[@id="-2"]')
    if sidewalk is None or sidewalk.attrib.get('type') != 'sidewalk':
        raise ValueError('Authored sidewalk lane absent')
    return {'case_id': config['case_id'], 'frames': 600,
            'cameras': list(CAMERAS), 'sidewalk_lane_id': -2,
            'rider_device_blueprint_filter': config['device_blueprint_filter'],
            'microphone_required': True, 'native_imported': False,
            'physical_and_legal_observation': False}


class RiderPolicy:
    def __init__(self, config):
        self.signal_frame = config['signal_frame']
        self.pause_window = tuple(config['pause_window_frames'])

    def request(self, frame):
        return {'forward_speed_mps': 0.0 if self.pause_window[0] <= frame < self.pause_window[1] else 1.4,
                'audible_signal_request': self.signal_frame is not None and frame == self.signal_frame}


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output/'sidewalk-actors.jsonl').exists():
        raise ValueError('New materialized original attempt required')
    microphone_device = os.environ.get(config.get('pedestrian_microphone', {}).get(
        'alsa_device_env',''), '')
    if not microphone_device:
        raise ValueError('Explicit live pedestrian microphone device required')
    speaker_device=os.environ.get(config.get('rider_speaker_alsa_device_env',''), '')
    if config['signal_frame'] is not None and not speaker_device:
        raise ValueError('Explicit live rider signal output required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    previous = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in previous.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned, encoders, camera_queues = [], {}, {}
    capture = None
    microphone = None
    encoder_exits = {}
    changed = False
    try:
        world = client.generate_opendrive_world((HERE/'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=25, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/20
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        road_map = world.get_map()
        sidewalk = road_map.get_waypoint(carla.Location(x=0, y=-5, z=.5),
            project_to_road=True, lane_type=carla.LaneType.Sidewalk)
        if sidewalk is None or sidewalk.road_id != 1 or sidewalk.lane_id != -2:
            raise RuntimeError('Original Native sidewalk lane readback failed')
        (output/'road.xodr').write_text(road_map.to_opendrive())
        (output/'sidewalk-map-readback.json').write_text(json.dumps({
            'source_kind':'original_native_map_readback', 'road_id':sidewalk.road_id,
            'lane_id':sidewalk.lane_id, 'lane_type':str(sidewalk.lane_type),
            'rider_device_class_verified':False,
            'municipal_applicability_verified':False}, indent=2)+'\n')
        library = world.get_blueprint_library()
        bicycles = library.filter(config['device_blueprint_filter'])
        if len(bicycles) != 1:
            raise RuntimeError('Pinned bicycle blueprint unavailable or ambiguous')
        bicycle_bp = bicycles[0]
        bicycle_bp.set_attribute('role_name','c230266_rider')
        bicycle = world.spawn_actor(bicycle_bp, carla.Transform(
            carla.Location(x=-10,y=-4.5,z=1.0),carla.Rotation(yaw=0)))
        owned.append(bicycle)
        pedestrians = library.filter(config['pedestrian_blueprint_filter'])
        if not pedestrians:
            raise RuntimeError('Pedestrian blueprint unavailable')
        pedestrian = world.spawn_actor(pedestrians[0], carla.Transform(
            carla.Location(x=0,y=-5.7,z=1.0),carla.Rotation(yaw=0)))
        owned.append(pedestrian)
        camera_mounts = {'overview':(-8,-18,28,-40),
                         'approach':(-10,-11,15,-25),
                         'reference_corner':(0,-12,12,-30),
                         'driver_reference':(8,-10,13,-25)}
        for name in CAMERAS:
            spec=next(c for c in config['cameras'] if c['name']==name)
            x,y,z,pitch=camera_mounts[name]
            bp=library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x',str(spec['width']))
            bp.set_attribute('image_size_y',str(spec['height']))
            bp.set_attribute('sensor_tick',str(1/20))
            camera=world.spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=z),
                carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q=queue.Queue();camera.listen(q.put);camera_queues[name]=q
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner',
                '-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgra','-s',
                f"{spec['width']}x{spec['height']}",'-r','20','-i','-',
                '-frames:v','600','-c:v','ffv1','-level','1',
                str(output/(name+'.mkv'))],stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        microphone=LiveMicrophone(output,microphone_device,pedestrian.id).start()
        policy=RiderPolicy(config)
        capture=PipelineCapture(client,bicycle,output,config['case_id'],
                                required_observations=[])
        with FrameMap(output/'video_frames.jsonl') as frame_map, \
                (output/'sidewalk-actors.jsonl').open('x') as actors, \
                (output/'camera-frames.jsonl').open('x') as camera_rows:
            initial_time=None
            for index in range(600):
                request=policy.request(index)
                bicycle.set_target_velocity(carla.Vector3D(
                    x=request['forward_speed_mps'],y=0,z=0))
                pedestrian.apply_control(carla.WalkerControl(
                    direction=carla.Vector3D(1,0,0),speed=.8))
                if request['audible_signal_request']:
                    # This emits through a live rider-positioned output device.
                    # Independent review must verify placement and actual sound.
                    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel',
                        'error','-f','lavfi','-i','sine=frequency=1000:duration=0.25',
                        '-f','alsa',speaker_device],
                        check=True,timeout=10)
                native_frame=world.tick()
                snap=world.get_snapshot()
                if snap.frame!=native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if initial_time is None:initial_time=snap.timestamp.elapsed_seconds
                time_s=snap.timestamp.elapsed_seconds-initial_time
                image_frames={}
                for name,q in camera_queues.items():
                    image=q.get(timeout=30)
                    while image.frame<native_frame:image=q.get(timeout=30)
                    if image.frame!=native_frame:
                        raise RuntimeError('Original source camera/frame mismatch: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    image_frames[name]=image.frame
                    camera_rows.write(json.dumps({'video_frame':index,'camera':name,
                        'native_frame':native_frame,
                        'rgb_sha256':hashlib.sha256(image.raw_data).hexdigest()})+'\n')
                frame_map.append(native_frame,time_s,camera_native_frames=image_frames)
                microphone.mark_frame(index,native_frame)
                bt,pt=bicycle.get_transform(),pedestrian.get_transform()
                bv,pv=bicycle.get_velocity(),pedestrian.get_velocity()
                be,pe=bicycle.bounding_box.extent,pedestrian.bounding_box.extent
                actors.write(json.dumps({'video_frame':index,'native_frame':native_frame,
                    'time_s':time_s,'rider_id':bicycle.id,'pedestrian_id':pedestrian.id,
                    'rider_device_blueprint':bicycle.type_id,
                    'rider_xyz_m':[bt.location.x,bt.location.y,bt.location.z],
                    'pedestrian_xyz_m':[pt.location.x,pt.location.y,pt.location.z],
                    'rider_bbox_extent_xyz_m':[be.x,be.y,be.z],
                    'pedestrian_bbox_extent_xyz_m':[pe.x,pe.y,pe.z],
                    'rider_yaw_deg':bt.rotation.yaw,'pedestrian_yaw_deg':pt.rotation.yaw,
                    'rider_velocity_xyz_mps':[bv.x,bv.y,bv.z],
                    'pedestrian_velocity_xyz_mps':[pv.x,pv.y,pv.z],
                    'signal_request':request['audible_signal_request'],
                    'requested_speed_mps':request['forward_speed_mps'],
                    'device_class_independently_verified':False,
                    'audio_placement_independently_verified':False})+'\n')
                capture.capture(native_frame,time_s,extra={'c230266_sidewalk':{
                    'rider_id':bicycle.id,'pedestrian_id':pedestrian.id,
                    'camera_native_frames':image_frames}})
        microphone.finish()
        microphone=None
        for name,encoder in encoders.items():
            encoder.stdin.close()
            err=encoder.stderr.read()
            encoder_exits[name]=encoder.wait(timeout=180)
            if encoder_exits[name] or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original source video encoding failed: '+name+': '+err.decode()[-300:])
        capture.close(confirmed=True);capture=None
        return {'frames':600,'source_cameras':list(CAMERAS),
                'original_audio_recorded':True,
                'physical_and_legal_observation':False}
    finally:
        if microphone is not None and microphone.process is not None:
            microphone.process.kill();microphone.process.wait()
        if capture is not None:capture.close(confirmed=False)
        for encoder in encoders.values():
            if encoder.poll() is None:encoder.kill();encoder.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restored=restore(client,saved)
            if capture is None and len(encoder_exits)==len(CAMERAS):
                seal_capture(output,frames=600,restoration=restored,errors=[],
                             encoder_exit_codes=encoder_exits,
                             context={'case_id':config['case_id']})
                record_native_exit(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args = parser.parse_args()
    config = json.loads((HERE/'config.json').read_text())
    summary = check(config)
    policy = RiderPolicy(config)
    assert len([policy.request(i) for i in range(600)]) == 600
    if args.check:
        print(json.dumps(summary, sort_keys=True))
    else:
        if not args.output_dir:raise SystemExit('--output-dir required')
        print(json.dumps(execute(config,args.output_dir,args.host,args.port)))


if __name__ == '__main__':
    main()
