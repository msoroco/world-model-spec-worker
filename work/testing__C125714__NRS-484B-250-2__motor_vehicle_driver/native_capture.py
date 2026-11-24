"""Reviewed, original Native two-vehicle capture for C125714.

No legal or physical-success finding is made by this acquisition path. A separate
source packet must be supplied before the first CARLA call.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from native_body_capture import append_pair, capture_pair
from controlled_yielding import Controller


CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def reviewed_context(scene, road):
    """Bind authority, geometry and original source bytes before Native execution."""
    descriptor = scene.get('reviewed_context')
    if descriptor is None and os.environ.get('SCENARIO_REVIEWED_CONTEXT_DESCRIPTOR'):
        descriptor_path = Path(os.environ['SCENARIO_REVIEWED_CONTEXT_DESCRIPTOR'])
        descriptor = json.loads(descriptor_path.read_text(encoding='utf-8'))
    if not isinstance(descriptor, dict):
        raise ValueError('separately reviewed C125714 context descriptor missing')
    source = Path(descriptor.get('source_path', ''))
    if (not source.is_file() or source.is_symlink() or
            sha(source) != descriptor.get('sha256') or
            not descriptor.get('reviewer') or not descriptor.get('source_citation')):
        raise ValueError('reviewed C125714 context bytes or provenance missing')
    packet = json.loads(source.read_text(encoding='utf-8'))
    identity = ('assignment_id', 'cell_id', 'case_id', 'map_sha256', 'crossing_id',
                'roadway_id', 'ego_highway', 'other_highway', 'ego_side', 'other_side',
                'approach_relation', 'official_device_controls_intersection',
                'other_left_turn_intent', 'subsection_4_context_reviewed',
                'intersection_polygon_xy_m', 'ego_route_xyz_m', 'other_route_xyz_m')
    reviewable = {'crossing_id', 'roadway_id', 'official_device_controls_intersection',
                  'other_left_turn_intent', 'subsection_4_context_reviewed'}
    for key in identity:
        expected = ('testing__C125714__NRS-484B-250-2__motor_vehicle_driver'
                    if key == 'assignment_id' else
                    scene.get('map_source_sha256') if key == 'map_sha256' else scene.get(key))
        if key in reviewable and expected in (None, 'unreviewed', False):
            continue
        if packet.get(key) != expected:
            raise ValueError('reviewed crossing differs from selected scene: ' + key)
    for key in ('reviewer', 'map_source_citation', 'highway_source_citation',
                'device_source_citation'):
        if not isinstance(packet.get(key), str) or not packet[key]:
            raise ValueError('reviewed site context missing: ' + key)
    if packet['map_sha256'] != sha(road):
        raise ValueError('reviewed OpenDRIVE identity differs')
    suffix = scene['case_id'].split('__')[-1]
    if packet['subsection_4_context_reviewed'] is not True:
        raise ValueError('subsection-4 qualification unreviewed')
    if suffix == 'official_device_controlled':
        signals = ET.fromstring(road.read_bytes()).findall('.//signal')
        if (packet['ego_highway'] == packet['other_highway'] or
                packet['approach_relation'] != 'crossing' or
                packet['official_device_controls_intersection'] is not True or
                not any(s.get('id') == packet.get('official_device_id') for s in signals)):
            raise ValueError('source-reviewed governing device missing from live map')
    elif suffix in ('opposite_intends_left','opposite_makes_left'):
        from exception_construction import heading
        ego = heading(packet['ego_route_xyz_m'],0,1)
        other = heading(packet['other_route_xyz_m'],0,1)
        if (packet['ego_highway'] != packet['other_highway'] or
                packet['approach_relation'] != 'opposite' or
                packet['official_device_controls_intersection'] is not False or
                packet['other_left_turn_intent'] is not True or
                packet.get('other_left_turn_making') is not
                    (suffix == 'opposite_makes_left') or
                sum(a*b for a,b in zip(ego,other)) >= -0.8):
            raise ValueError('source-reviewed opposite left-turn context missing')
        if suffix == 'opposite_makes_left':
            end = heading(packet['other_route_xyz_m'],1,2)
            if other[0]*end[1]-other[1]*end[0] <= .7:
                raise ValueError('source-reviewed left-turn route geometry missing')
    elif (packet['ego_highway'] == packet['other_highway'] or
            packet['ego_side'] != 'left' or packet['other_side'] != 'right' or
            packet['approach_relation'] != 'crossing' or
            packet['official_device_controls_intersection'] is not False or
            packet['other_left_turn_intent'] is not False):
        raise ValueError('different-highway left/right and exception context unreviewed')
    retained = {}
    for key in ('map_source', 'highway_source', 'device_source',
                'intersection_source', 'driver_source'):
        item = packet.get(key)
        if not isinstance(item, dict):
            raise ValueError('reviewed ' + key + ' source descriptor missing')
        relative = item.get('path', '')
        if (not relative or Path(relative).is_absolute() or '..' in Path(relative).parts or
                not item.get('reviewer') or not item.get('citation')):
            raise ValueError('reviewed ' + key + ' source provenance missing')
        original = source.parent / relative
        if (not original.is_file() or original.is_symlink() or
                not original.resolve().is_relative_to(source.parent.resolve()) or
                sha(original) != item.get('sha256')):
            raise ValueError('reviewed ' + key + ' source bytes missing or changed')
        retained[key] = original
    return source, packet, retained


class CameraBank:
    """Four synchronized original RGB streams, retained as lossless FFV1."""
    def __init__(self, world, ego, output, carla, scene):
        self.sensors, self.encoders, self.queues, self.errors = [], {}, {}, []
        self.closed = False
        polygon = scene['intersection_polygon_xy_m']
        cx = sum(p[0] for p in polygon) / len(polygon)
        cy = sum(p[1] for p in polygon) / len(polygon)
        ego_start = scene['ego_route_xyz_m'][0]
        other_start = scene['other_route_xyz_m'][0]
        poses = {'overview': (cx, cy, 45, -90, 0),
                 'approach': (ego_start[0]-3, ego_start[1], 11, -20, 0),
                 'reference_corner': (other_start[0]-5, other_start[1]-3, 11, -25, 65),
                 'driver_reference': (1.2, 0, 1.5, -2, 0)}
        try:
            for name, width, height in CAMERAS:
                bp = world.get_blueprint_library().find('sensor.camera.rgb')
                for key, value in (('image_size_x', width), ('image_size_y', height),
                                   ('fov', 75)):
                    bp.set_attribute(key, str(value))
                x, y, z, pitch, yaw = poses[name]
                transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                            carla.Rotation(pitch=pitch, yaw=yaw))
                sensor = world.spawn_actor(bp, transform,
                        attach_to=ego if name == 'driver_reference' else None)
                if sensor is None:
                    raise RuntimeError('Native camera spawn failed: ' + name)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames
                def receive(image, q=frames, label=name):
                    try:
                        q.put_nowait(image)
                    except queue.Full:
                        self.errors.append('camera queue overflow: ' + label)
                sensor.listen(receive)
                self.encoders[name] = subprocess.Popen(
                    ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                     '-f', 'rawvideo', '-pixel_format', 'bgra', '-video_size',
                     f'{width}x{height}', '-framerate', '20', '-i', 'pipe:0', '-an',
                     '-c:v', 'ffv1', '-pix_fmt', 'bgra', str(output / (name+'.mkv'))],
                    stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError('; '.join(self.errors))
        images = {}
        for name, width, height in CAMERAS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame or image.width != width or image.height != height:
                raise RuntimeError('camera identity/dimension mismatch: ' + name)
            raw = image.raw_data
            if len(raw) != width * height * 4:
                raise RuntimeError('camera BGRA byte count differs: ' + name)
            images[name] = raw
        for name, _, _ in CAMERAS:
            self.encoders[name].stdin.write(images[name])

    def close(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as exc:
                errors.append(repr(exc))
        for name, process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=180):
                    errors.append('camera encoder failed: ' + name)
            except BaseException as exc:
                errors.append(repr(exc))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as exc:
                errors.append(repr(exc))
        if errors:
            raise RuntimeError('; '.join(errors))


def run_native(scene, road, output, host, port):
    """Capture source-bound originals after a real reviewed packet is supplied."""
    source, packet, retained = reviewed_context(scene, road)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import equal, fields

    output = Path(output).resolve()
    if not output.is_dir() or not (output/'construction.json').is_file():
        raise ValueError('materialized Native attempt directory required')
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.generate_opendrive_world(Path(road).read_text(encoding='utf-8'))
    if hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() != packet['map_sha256']:
        raise ValueError('generated Native map differs from reviewed OpenDRIVE')
    original = world.get_settings()
    actors = []
    cameras = capture = frame_map = None
    frames, phase, error = [], 'initializing', None
    restored = False
    try:
        shutil.copyfile(source, output/'reviewed-context.json')
        for key, path in retained.items():
            folder = output/'context_sources';folder.mkdir(exist_ok=True)
            shutil.copyfile(path, folder/(key+'.bin'))
        (output/'road.xodr').write_text(world.get_map().to_opendrive(), encoding='utf-8')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        named = {}
        for name in ('ego', 'other'):
            route = scene[name+'_route_xyz_m']
            direction = (route[1][0]-route[0][0],route[1][1]-route[0][1])
            yaw = math.degrees(math.atan2(direction[1],direction[0]))
            waypoint = world.get_map().get_waypoint(carla.Location(x=route[0][0], y=route[0][1], z=route[0][2]), project_to_road=False)
            if waypoint is None or str(waypoint.lane_type).lower().find('driving') < 0:
                raise ValueError(name+' initial point lacks original driving lane')
            bp = library.find(scene[name+'_blueprint_id'])
            actor = world.spawn_actor(bp, carla.Transform(carla.Location(x=route[0][0],y=route[0][1],z=waypoint.transform.location.z+.5),carla.Rotation(yaw=yaw)))
            if actor is None:
                raise RuntimeError(name+' Native spawn failed')
            actors.append(actor);named[name]=actor
        if named['ego'].id == named['other'].id:
            raise ValueError('original vehicle identities coincide')
        context = dict(packet, ego_actor_id=int(named['ego'].id),
                       other_actor_id=int(named['other'].id))
        write(output/'site-context.json', context)
        write(output/'acquisition-provenance.json', {'provenance_kind':'native',
              'diagnostic_fixture':False,'reviewed_context_sha256':sha(output/'reviewed-context.json')})
        cameras = CameraBank(world,named['ego'],output,carla,scene)
        capture = PipelineCapture(client,named['ego'],output,scene['case_id'])
        frame_map = FrameMap(output/'video_frames.jsonl')
        offset = scene['requested_entry_offset_s']
        other_release = 1.0 + max(0.0,-offset)
        ego_release = other_release + offset
        controller = Controller(scene.get('control_policy','timed_release'),
                                scene['intersection_polygon_xy_m'],
                                ego_release,other_release)
        count = round(scene['duration_s']*scene['capture_rate_hz'])
        phase = 'capturing'
        with (output/'ego-body-history.jsonl').open('x',buffering=1) as ego_stream, \
             (output/'other-body-history.jsonl').open('x',buffering=1) as other_stream, \
             (output/'controller-history.jsonl').open('x',buffering=1) as control_stream:
            start_time = None
            for index in range(count):
                elapsed = 0 if start_time is None else index*.05
                controls = controller.controls(elapsed)
                if scene['case_id'].endswith('__opposite_makes_left'):
                    actor = named['other']
                    here = actor.get_transform().location
                    target = scene['other_route_xyz_m'][1 if math.hypot(
                        here.x-scene['other_route_xyz_m'][1][0],
                        here.y-scene['other_route_xyz_m'][1][1]) > 4 else 2]
                    desired = math.degrees(math.atan2(target[1]-here.y,target[0]-here.x))
                    error = (desired-actor.get_transform().rotation.yaw+180)%360-180
                    controls['other']['steer'] = max(-.65,min(.65,error/50))
                for name in ('ego','other'):
                    named[name].apply_control(carla.VehicleControl(**controls[name]))
                frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != frame:
                    raise RuntimeError('Native world tick identity differs')
                time_s = snapshot.timestamp.elapsed_seconds
                if start_time is None:
                    start_time = time_s
                capture.capture(frame,time_s)
                cameras.append(frame)
                frame_map.append(frame,time_s)
                pair = capture_pair(snapshot,named)
                controller.update_other(pair['other']['body_vertices_xy_m'])
                append_pair({'ego':ego_stream,'other':other_stream},pair)
                control_stream.write(json.dumps({'frame':frame,'time_s':time_s,
                    'ego_release_s':ego_release,'other_release_s':other_release,
                    'ego_brake':named['ego'].get_control().brake,
                    'other_brake':named['other'].get_control().brake,
                    'control_policy':controller.policy,
                    'other_entered':controller.other_entered,
                    'other_cleared':controller.other_cleared,
                    'release_schedule_is_training_target_only':True})+'\n')
                frames.append(frame)
        phase = 'closing'
        capture.close();capture=None
        frame_map.close();frame_map=None
        cameras.close();cameras=None
        originals = ('road.xodr','site-context.json','ego-body-history.jsonl',
                     'other-body-history.jsonl','trace.jsonl','video_frames.jsonl',
                     'controller-history.jsonl',*(name+'.mkv' for name,_,_ in CAMERAS))
        sources = {name:{'kind':'original_native','sha256':sha(output/name)} for name in originals}
        write(output/'source-manifest.json',sources)
        write(output/'acquisition.json',sources)
        phase = 'sealed'
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        cleanup=[]
        for resource in (capture,frame_map,cameras):
            if resource is not None:
                try:resource.close()
                except BaseException as exc:cleanup.append(repr(exc))
        for actor in reversed(actors):
            try:actor.destroy()
            except BaseException as exc:cleanup.append(repr(exc))
        try:
            world.apply_settings(original)
            restored=all(equal(fields(world.get_settings()).get(k),v)
                         for k,v in fields(original).items())
        except BaseException as exc:cleanup.append(repr(exc))
        if phase=='sealed' and not cleanup and restored:
            seal_capture(output,frames=len(frames),restoration={'restored':True,
                'settings_readback':'synchronous_mode and fixed_delta_seconds restored'},
                errors=[],encoder_exit_codes={name:0 for name,_,_ in CAMERAS},
                context={'crossing_id':packet['crossing_id'],
                         'reviewed_context_sha256':sha(output/'reviewed-context.json')})
        else:
            write(output/'native-run-status.json',{'phase':phase,
                  'errors':[x for x in [error,*cleanup] if x],
                  'settings_restored':restored})
            if phase=='sealed':
                raise RuntimeError('Native cleanup or settings restoration failed')
