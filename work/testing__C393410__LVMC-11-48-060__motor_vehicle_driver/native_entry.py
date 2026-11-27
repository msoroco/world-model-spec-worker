"""Capture source-reviewed passage between truck routes with world restoration."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from queue import Empty, Queue
import shutil
import subprocess

from route_measure import load_review, sha
from route_adapter import configure, step, sample, teardown

CAMERAS={'overview':(1920,1080),'approach':(1280,720),'reference_corner':(1280,720),'driver_reference':(1280,720)}


def write(path:Path,value:dict)->None:
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def camera(world,carla,pose,name,queue):
    blueprint=world.get_blueprint_library().find('sensor.camera.rgb')
    width,height=CAMERAS[name]
    blueprint.set_attribute('image_size_x',str(width));blueprint.set_attribute('image_size_y',str(height));blueprint.set_attribute('sensor_tick','0.05')
    xyz,pyr=pose['location_xyz_m'],pose['pitch_yaw_roll_deg']
    actor=world.try_spawn_actor(blueprint,carla.Transform(carla.Location(*xyz),carla.Rotation(pitch=pyr[0],yaw=pyr[1],roll=pyr[2])))
    if actor is None:raise RuntimeError('Original truck-route camera spawn failed: '+name)
    actor.listen(lambda image:queue.put(image));return actor


def encoder(path,width,height):
    return subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','bgra','-video_size',f'{width}x{height}','-framerate','20','-i','pipe:0','-c:v','ffv1',str(path)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)


def image(queue,expected):
    try:value=queue.get(timeout=15)
    except Empty as error:raise RuntimeError('Synchronized truck-route camera frame missing') from error
    if value.frame!=expected:raise ValueError('Original camera frame identity differs')
    return value


def capture_original(root,attempt,review_path,source_root,*,host='127.0.0.1',port=2000):
    root,attempt,review_path,source_root=map(lambda x:Path(x).resolve(),(root,attempt,review_path,source_root))
    config=json.loads((root/'config.json').read_text());spec=json.loads((root/'case-spec.json').read_text());control=json.loads((root/'controller.json').read_text())
    case_id=config['selected_case_id']
    if spec.get('case_id')!=case_id:raise ValueError('Exact route case differs')
    if not attempt.is_dir() or any((attempt/name).exists() for name in ('trace.jsonl','video_frames.jsonl','original-route-observations.json','original-route-receipt.json','result.json')):
        raise ValueError('Fresh materialized Native attempt required')
    packet=load_review(review_path,source_root,case_id)
    if (packet['site']['intervening_street']['designation']!=spec['street_class'] or packet['itinerary']['route_use']!=spec['route_use'] or packet['enroute_purpose']['kind']!=spec['enroute_purpose']):
        raise ValueError('Reviewed route comparison variable differs')
    by_path={row['path']:row for row in packet['source_provenance']['files']}
    opendrive=packet.get('opendrive_source_path')
    if not opendrive or opendrive not in by_path:raise ValueError('Original OpenDRIVE source not inventoried')
    poses=packet.get('cameras',{})
    if set(poses)!=set(CAMERAS):raise ValueError('All four reviewed original camera poses required')
    for name,row in poses.items():
        if len(row.get('location_xyz_m',[]))!=3 or len(row.get('pitch_yaw_roll_deg',[]))!=3:
            raise ValueError('Original camera pose incomplete: '+name)
    shutil.copy2(review_path,attempt/'reviewed-route.json')
    for source in by_path.values():
        target=attempt/'reviewed-sources'/source['path'];target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source_root/source['path'],target)
    if 'SCENARIO_PIPELINE_OUTPUT_ROOT' not in os.environ:raise ValueError('Runtime output root required before Native import')
    import carla
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore
    client=carla.Client(host,int(port));client.set_timeout(30);prior=snapshot(client)
    cameras={};queues={};encoders={};handle=None;frame_map=None;failure=None;restored=False
    try:
        world=client.generate_opendrive_world((source_root/opendrive).read_text())
        live_sha=hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
        if live_sha!=by_path[opendrive]['sha256']:raise ValueError('Native OpenDRIVE readback differs from reviewed source')
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;settings.no_rendering_mode=False;world.apply_settings(settings)
        handle=configure(world,carla,packet,float(control['target_speed_mps']))
        for name,(width,height) in CAMERAS.items():
            queues[name]=Queue();cameras[name]=camera(world,carla,poses[name],name,queues[name]);encoders[name]=encoder(attempt/(name+'.mkv'),width,height)
        frame_map=FrameMap(attempt/'video_frames.jsonl');observations=[]
        with (attempt/'trace.jsonl').open('x',buffering=1) as trace:
            for _ in range(900):
                step(handle,carla)
                frame=world.tick();time_s=float(world.get_snapshot().timestamp.elapsed_seconds)
                frame_map.append(frame,time_s)
                row=sample(world,handle,packet,frame,time_s)
                observations.append(row)
                trace.write(json.dumps({'frame':frame,'time_s':time_s,'actor_id':row['ego_actor_id'],'position_m':row['position_xy_m']},allow_nan=False)+'\n')
                for name in CAMERAS:encoders[name].stdin.write(bytes(image(queues[name],frame).raw_data))
        for process in encoders.values():
            process.stdin.close()
            if process.wait(timeout=120)!=0:raise RuntimeError('Four-view truck-route encoder failed')
        frame_map.close()
        data={'assignment_id':root.name,'case_id':case_id,'original_trace_id':'Native:'+sha(attempt/'trace.jsonl'),'diagnostic_fixture':False,
            'site_source_sha256':sha(review_path),'site':packet['site'],'itinerary':packet['itinerary'],'enroute_purpose':packet['enroute_purpose'],'fps':20,'frames':observations}
        write(attempt/'original-route-observations.json',data)
        write(attempt/'original-route-receipt.json',{'case_id':case_id,'fps':20,'frame_count':900,'diagnostic_fixture':False,'source_sha256':sha(attempt/'original-route-observations.json'),'review_sha256':sha(review_path)})
    except BaseException as error:failure=error
    finally:
        if frame_map is not None and not frame_map.stream.closed:frame_map.close()
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in cameras.values():
            try:actor.stop()
            finally:actor.destroy()
        if handle is not None:
            try:teardown(handle)
            except BaseException as error:failure=failure or error
        try:restored=bool(restore(client,prior)['restored'])
        except BaseException as error:failure=failure or error
    write(attempt/'native-run-status.json',{'restored':restored,'capture_complete':failure is None,'errors':[repr(failure)] if failure else []})
    if failure or not restored:raise RuntimeError('Original truck-route capture or restoration failed') from failure
    write(attempt/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':False,'case_id':case_id,'review_sha256':sha(review_path)})
    seal_capture(attempt,frames=900,restoration={'restored':True},errors=[],encoder_exit_codes={name:0 for name in CAMERAS},context={'case_id':case_id,'review_sha256':sha(review_path),'legal_verdict_claimed':False})
    return {'case_id':case_id,'frame_count':900,'restored':True,'original_route_source_sha256':sha(attempt/'original-route-observations.json'),'physical_acceptance':False}
