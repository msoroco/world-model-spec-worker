"""Prospective original 30-second parked-vehicle lamp capture.

Lamp requests, weather and stopped speed are recorded separately from optical,
nighttime, highway and lawful-parking findings made on saved original sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import queue
import shutil
import subprocess
from pathlib import Path

from controller import CASE_MODES, FRAMES, RATE_HZ, apply_light_request
from lamp_source_measure import CAMERAS

BASE = 'training__C229422__NRS-484B-473-2__motor_vehicle_driver__'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    case = config.get('case_id', '')
    require(case.startswith(BASE) and case[len(BASE):] in CASE_MODES,
            'Unknown exact parked-lamp case')
    require((config.get('law_id'), config.get('cell_id'), config.get('actor')) ==
            ('NRS-484B-473-2', 'C229422', 'motor_vehicle_driver'),
            'Wrong law, cell or actor')
    require(config.get('frozen_cell') ==
            {'layout':'road','maneuver':'park','control':'lane_marking'},
            'Wrong frozen cell')
    require(config.get('duration_frames') == FRAMES and
            config.get('rate_hz') == RATE_HZ and config.get('duration_s') == 30,
            'Full nighttime parked interval required')
    require(config.get('mode') == CASE_MODES[case[len(BASE):]],
            'Selected lamp alternative differs')
    cameras = config.get('cameras')
    require(isinstance(cameras,list) and tuple(c['name'] for c in cameras) == CAMERAS and
            [(c['width'],c['height']) for c in cameras] ==
            [(1920,1080),(1280,720),(1280,720),(1280,720)],
            'Four-view original camera profile required')
    require(all(c.get('fps') == RATE_HZ and c.get('pose_strategy') and
                c.get('fov_deg') and len(c.get('location_xyz_m',[])) == 3 and
                len(c.get('rotation_pyr_deg',[])) == 3 for c in cameras),
            'Camera cadence, optics or source-bound pose missing')
    require(config.get('vehicle_blueprint') == 'vehicle.tesla.model3' and
            config.get('physical_verified') is False and
            config.get('legal_verdict') is None,
            'Lamp command cannot prove optical or legal result')
    return {'case_id':case,'frames':FRAMES,'mode_request':config['mode'],
            'carla_contacted':False,'physical_verified':False}


def validate_scene(review, config):
    require(review.get('case_id') == config['case_id'] and
            review.get('source_kind') == 'original_scene_setup',
            'Exact original scene setup required')
    require(review.get('map_name') and type(review.get('ego_spawn_index')) is int and
            review['ego_spawn_index'] >= 0 and review.get('parking_position_review') and
            review.get('civil_clock_source') and review.get('sunset_sunrise_source') and
            review.get('highway_source') and review.get('parking_rule_source'),
            'Original map, highway, parking and civil-night setup sources required')
    require(review.get('requested_sun_altitude_deg') < 0 and
            review.get('civil_start_iso') and review.get('sunset_iso') and
            review.get('sunrise_iso'),
            'Nighttime weather and offset-aware civil clock request required')
    require(review.get('physical_verified') is False and
            review.get('lawfully_parked_verified') is False,
            'Prospective setup cannot claim physical or lawful parking success')
    sources = review.get('sources', {})
    require(set(sources) == {'highway','parking_rule','civil_clock','sunset_sunrise'},
            'Four original setup source references required')
    for name,ref in sources.items():
        path=Path(ref['path'])
        require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'],
                'Original setup source changed: '+name)
    return review


def _camera_pose(carla,camera):
    x,y,z=camera['location_xyz_m'];pitch,yaw,roll=camera['rotation_pyr_deg']
    return carla.Transform(carla.Location(x=x,y=y,z=z),
                           carla.Rotation(pitch=pitch,yaw=yaw,roll=roll))


def _speed(actor):
    v=actor.get_velocity();return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)


def execute(config, output_dir, review_path, host, port):
    check(config)
    require(review_path, 'Original scene review path required')
    review=validate_scene(json.loads(Path(review_path).read_text()),config)
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    root=Path(output_dir)
    require(root.is_dir() and (root/'config.json').is_file(),
            'Runtime-materialized Native bundle required')
    for name,ref in review['sources'].items():
        shutil.copyfile(ref['path'],root/('original-'+name+'.json'))
    (root/'original-scene-review.json').write_text(json.dumps(review,indent=2,allow_nan=False)+'\n')
    client=carla.Client(host,port);client.set_timeout(15)
    world=client.get_world();saved=snapshot(client)
    actors=[];sensors=[];encoders={};logs={};packets=queue.Queue();exit_codes={}
    restoration=None
    try:
        require(world.get_map().name == review['map_name'],
                'Reviewed map differs from Native world')
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=1/RATE_HZ;world.apply_settings(settings)
        weather=world.get_weather();weather.sun_altitude_angle=review['requested_sun_altitude_deg']
        world.set_weather(weather)
        spawns=world.get_map().get_spawn_points()
        require(review['ego_spawn_index'] < len(spawns),'Reviewed parked spawn unavailable')
        blueprints=world.get_blueprint_library()
        ego=world.try_spawn_actor(blueprints.find(config['vehicle_blueprint']),
                                  spawns[review['ego_spawn_index']])
        require(ego is not None,'Parked vehicle spawn failed')
        actors.append(ego)
        for camera in config['cameras']:
            bp=blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x',str(camera['width']))
            bp.set_attribute('image_size_y',str(camera['height']))
            bp.set_attribute('fov',str(camera['fov_deg']))
            sensor=world.spawn_actor(bp,_camera_pose(carla,camera),attach_to=ego)
            actors.append(sensor);sensors.append(sensor)
            name=camera['name'];logs[name]=(root/(name+'.encoder.log')).open('x')
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                '-n','-f','rawvideo','-pix_fmt','rgb24','-s',f"{camera['width']}x{camera['height']}",
                '-r',str(RATE_HZ),'-i','pipe:0','-an','-c:v','ffv1',str(root/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=logs[name])
            sensor.listen(lambda image,view=name:packets.put((view,image)))
        suffix=config['case_id'][len(BASE):]
        with PipelineCapture(client,ego,root,config['case_id'],
                             required_observations=config.get('required_atoms',[])) as capture, \
             FrameMap(root/'video_frames.jsonl') as frame_map, \
             (root/'parked-lamp-trace.jsonl').open('x',buffering=1) as trace:
            for i in range(FRAMES):
                request=apply_light_request(ego,carla,suffix,i)
                ego.apply_control(carla.VehicleControl(brake=1.0,hand_brake=True))
                native_frame=world.tick();seen=set()
                while len(seen)<len(CAMERAS):
                    name,image=packets.get(timeout=15)
                    if image.frame!=native_frame or name in seen:continue
                    camera=next(c for c in config['cameras'] if c['name']==name)
                    bgra=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        camera['height'],camera['width'],4)
                    encoders[name].stdin.write(bgra[:,:,:3][:,:,::-1].tobytes())
                    seen.add(name)
                elapsed=world.get_snapshot().timestamp.elapsed_seconds
                frame_map.append(native_frame,i/RATE_HZ,native_elapsed_s=elapsed)
                capture.capture(native_frame,i/RATE_HZ,extra={
                    'video_frame':i,'lamp_request':request['mode_request']})
                waypoint=world.get_map().get_waypoint(ego.get_transform().location,
                    project_to_road=True,lane_type=carla.LaneType.Any)
                trace.write(json.dumps({'source_kind':'original_native_observation',
                    'video_frame':i,'native_frame':native_frame,'native_elapsed_s':elapsed,
                    'time_s':i/RATE_HZ,'vehicle_actor_id':ego.id,
                    'road_id':waypoint.road_id if waypoint else None,
                    'lane_id':waypoint.lane_id if waypoint else None,
                    'ego_speed_mps':_speed(ego),'headlamp_request':request['mode_request'],
                    'native_light_state_readback':str(ego.get_light_state()),
                    'optical_state_observed':None,'lawfully_parked_observed':None})+'\n')
    finally:
        failures=[]
        for sensor in sensors:
            try:sensor.stop()
            except BaseException as exc:failures.append('sensor stop: '+str(exc))
        for name,encoder in encoders.items():
            try:
                encoder.stdin.close();exit_codes[name]=encoder.wait(timeout=120)
                if exit_codes[name]!=0:failures.append('encoder failed: '+name)
            except BaseException as exc:failures.append('encoder close: '+str(exc))
            finally:logs[name].close()
        for actor in reversed(actors):
            try:actor.destroy()
            except BaseException as exc:failures.append('actor destroy: '+str(exc))
        try:restoration=restore(client,saved)
        except BaseException as exc:failures.append('world restore: '+str(exc))
        if failures:raise RuntimeError('; '.join(failures))
    (root/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'original_native','diagnostic_fixture':False,
        'case_id':config['case_id'],'source':'owned Native execution and four RGB cameras'},
        indent=2)+'\n')
    seal_capture(root,frames=FRAMES,restoration=restoration,errors=[],
        encoder_exit_codes=exit_codes,context={'case_id':config['case_id'],
        'physical_acceptance_claimed':False,'optical_state_observed_by_command':False})
    return {'case_id':config['case_id'],'frames_requested':FRAMES,
            'physical_verified':False,'legal_verdict':None}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--output-dir');p.add_argument('--scene-review')
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000)
    a=p.parse_args();config=json.loads(Path('config.json').read_text())
    if a.check:print(json.dumps(check(config),sort_keys=True))
    else:
        require(a.output_dir is not None,'--output-dir required')
        print(json.dumps(execute(config,a.output_dir,a.scene_review or
            os.environ.get('SCENARIO_LAMP_SCENE_REVIEW'),a.host,a.port),sort_keys=True))
