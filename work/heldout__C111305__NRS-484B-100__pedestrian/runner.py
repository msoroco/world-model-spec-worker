"""Native pedestrian/officer construction for seven exact C111305 response and cue-timing cases.

The command is a staged physical cue. Authority, lawful duty, perception and
willfulness stay open for independent review of original sources.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from threading import Condition
from time import monotonic

PREFIX = 'heldout__C111305__NRS-484B-100__pedestrian__'
CASES = {
    'stop_responds': ('stop', True),
    'stop_does_not_respond': ('stop', False),
    'proceed_responds': ('proceed', True),
    'proceed_does_not_respond': ('proceed', False),
}
TIMING_CASES = {
    'stop_responds_timing_early': ('stop', True),
    'stop_responds_timing_nominal': ('stop', True),
    'stop_responds_timing_late': ('stop', True),
}
TIMING_FRAMES = {'stop_responds_timing_early': 30, 'stop_responds_timing_nominal': 40, 'stop_responds_timing_late': 50}

CAMERAS = {
    'overview': ((-6, 0, 7), (-15, 0, 0), (1920, 1080), 95),
    'approach': ((1, 0, 2), (0, 0, 0), (1280, 720), 90),
    'reference_corner': ((-2, 2.5, 2.5), (-10, 0, 0), (1280, 720), 100),
    'driver_reference': ((0.5, -0.4, 1.6), (0, 0, 0), (1280, 720), 85),
}


def check_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != ('NRS-484B-100', 'C111305', 'pedestrian'):
        raise ValueError('Wrong frozen pedestrian officer scope')
    case = config.get('selected_case_id', '')
    suffix = case.removeprefix(PREFIX)
    if case != PREFIX + suffix or suffix not in (CASES | TIMING_CASES) or config.get('case', {}).get('case_id') != case:
        raise ValueError('Unknown exact pedestrian officer case')
    expected_frame = TIMING_FRAMES.get(suffix, 40)
    if config.get('rate_hz') != 20 or config.get('frames') != 160 or config.get('direction_frame') != expected_frame:
        raise ValueError('20 Hz direction and exact cue-timing contract changed')
    if [(c.get('name'), c.get('width'), c.get('height')) for c in config.get('cameras', [])] != [
        (name, spec[2][0], spec[2][1]) for name, spec in CAMERAS.items()]:
        raise ValueError('Four named source-camera plan changed')
    if not 0.5 <= float(config.get('walk_speed_mps', 1.2)) <= 1.8:
        raise ValueError('Unsupported pedestrian walk speed')
    if not 0 <= float(config.get('overview_height_delta_m', 0)) <= 2:
        raise ValueError('Unsupported overview mount change')
    return (CASES | TIMING_CASES)[suffix]


def choose_crosswalk(world_map, carla):
    """Find a bounded crosswalk with sidewalk waypoints near both ends."""
    points = list(world_map.get_crosswalks())
    candidates = []
    polygons, current = [], []
    for point in points:
        if current and math.hypot(point.x-current[0].x, point.y-current[0].y) < 0.05:
            if len(current) >= 3: polygons.append(current)
            current = []
        else:
            current.append(point)
    if current and len(current) >= 3: polygons.append(current)
    for polygon in polygons:
      for i, first in enumerate(polygon):
        for last in polygon[i + 1:]:
            distance = math.hypot(last.x-first.x, last.y-first.y)
            if not 4 <= distance <= 18:
                continue
            start = world_map.get_waypoint(first, project_to_road=True, lane_type=carla.LaneType.Sidewalk)
            end = world_map.get_waypoint(last, project_to_road=True, lane_type=carla.LaneType.Sidewalk)
            if start is None or end is None:
                continue
            if math.hypot(start.transform.location.x-first.x, start.transform.location.y-first.y) > 4:
                continue
            if math.hypot(end.transform.location.x-last.x, end.transform.location.y-last.y) > 4:
                continue
            midpoint = carla.Location((first.x+last.x)/2, (first.y+last.y)/2, first.z)
            roadway = world_map.get_waypoint(midpoint, project_to_road=True, lane_type=carla.LaneType.Driving)
            if roadway is None or not roadway.is_junction:
                continue
            candidates.append((distance, first, last, start, end))
    if not candidates:
        raise ValueError('No connected intersection crosswalk with adjacent sidewalks')
    _, first, last, start, end = max(candidates, key=lambda row: row[0])
    direction = ((last.x-first.x)/math.hypot(last.x-first.x, last.y-first.y),
                 (last.y-first.y)/math.hypot(last.x-first.x, last.y-first.y))
    return first, last, start, end, direction


def walker_speed(command, responds, frame, direction_frame, walk_speed):
    if frame < direction_frame:
        return walk_speed if command == 'stop' else 0.0
    if command == 'stop':
        return 0.0 if responds else walk_speed
    return walk_speed if responds else 0.0


def pose_direction(carla, officer, command, pitch_delta=0.0):
    names = [item[0] for item in officer.get_bones().bone_transforms]
    arms = [name for name in names if any(marker in name.lower() for marker in ('upperarm_r','upper_arm_r','rightupperarm'))]
    if len(arms) != 1:
        raise ValueError('Officer walker right upper-arm bone unavailable')
    angle = (95.0 if command == 'stop' else 35.0) + pitch_delta
    officer.set_bones(carla.WalkerBoneControlIn([(arms[0], carla.Transform(carla.Location(), carla.Rotation(pitch=angle)))]))
    officer.blend_pose(1.0)
    return {'bone': arms[0], 'relative_pitch_deg': angle, 'command': command}


class SourceSink:
    def __init__(self, root, name):
        width, height = CAMERAS[name][2]
        path = root / (name + '.mkv')
        if path.exists():
            raise ValueError('Original source stream already exists: ' + name)
        self.size = width * height * 4
        self.process = subprocess.Popen(['ffmpeg','-nostdin','-loglevel','error','-y','-f','rawvideo',
            '-pixel_format','bgra','-video_size',f'{width}x{height}','-framerate','20',
            '-i','pipe:0','-an','-c:v','ffv1',str(path)], stdin=subprocess.PIPE)
        self.closed = False

    def write(self, image):
        if len(image.raw_data) != self.size:
            raise ValueError('Original source camera dimensions changed')
        self.process.stdin.write(image.raw_data)

    def close(self):
        if not self.closed:
            self.closed = True
            self.process.stdin.close()
            if self.process.wait() != 0:
                raise ValueError('Original source camera encoder failed')


class SourceCameras:
    def __init__(self, world, carla, subject, sinks, overview_height_delta=0.0):
        self.condition = Condition()
        self.frames = {name: set() for name in CAMERAS}
        self.errors = []
        self.sensors = []
        self.sinks = sinks
        self.closed = False
        try:
            for name, (location, rotation, size, fov) in CAMERAS.items():
                blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
                for key, value in [('image_size_x',size[0]),('image_size_y',size[1]),('fov',fov),('sensor_tick',0.05)]:
                    blueprint.set_attribute(key, str(value))
                x,y,z = location
                if name == 'overview': z += overview_height_delta
                transform = carla.Transform(carla.Location(x,y,z), carla.Rotation(*rotation))
                sensor = world.spawn_actor(blueprint, transform, attach_to=subject)
                self.sensors.append(sensor)
                sensor.listen(lambda image, camera_name=name: self._receive(camera_name, image))
        except BaseException:
            self.close()
            raise

    def _receive(self, name, image):
        with self.condition:
            try:
                if image.frame in self.frames[name] or (image.width,image.height) != CAMERAS[name][2]:
                    raise ValueError('Duplicate or wrong-sized original camera frame: ' + name)
                self.sinks[name].write(image)
                self.frames[name].add(image.frame)
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.condition.notify_all()

    def wait(self, frame, timeout_s=10):
        deadline = monotonic() + timeout_s
        with self.condition:
            while not all(frame in rows for rows in self.frames.values()):
                if self.errors:
                    raise ValueError('Original camera callback failed') from self.errors[0]
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ValueError('Missing joined original camera frame: ' + str(frame))
                self.condition.wait(remaining)

    def verify(self, frames):
        if self.errors or any(rows != set(frames) for rows in self.frames.values()):
            raise ValueError('Original four-view frame set incomplete')

    def close(self):
        if not self.closed:
            self.closed = True
            for sensor in self.sensors:
                sensor.stop()
                sensor.destroy()


def run(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    output = Path(output)
    config = json.loads((output/'config.json').read_text())
    command, responds = check_config(config)
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    settings_before = world.get_settings()
    actors, sinks, cameras, capture, frame_map = [], {}, None, None, None
    failed = True
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        first, last, sidewalk_start, sidewalk_end, direction = choose_crosswalk(world.get_map(), carla)
        bp = world.get_blueprint_library().filter('walker.pedestrian.*')
        if len(bp) < 2:
            raise ValueError('Two Native walker blueprints required')
        origin = carla.Location(first.x-3*direction[0], first.y-3*direction[1], first.z)
        subject = world.try_spawn_actor(bp[0], carla.Transform(origin, sidewalk_start.transform.rotation))
        if subject is None:
            raise ValueError('Native pedestrian actor spawn failed')
        actors.append(subject)
        officer = world.try_spawn_actor(bp[1], sidewalk_start.transform)
        if officer is None:
            raise ValueError('Native officer actor spawn failed')
        actors.append(officer)
        officer.apply_control(carla.WalkerControl(speed=0.0))
        sinks = {name: SourceSink(output,name) for name in CAMERAS}
        cameras = SourceCameras(world,carla,subject,sinks,float(config.get('overview_height_delta_m',0)))
        capture = PipelineCapture(client,subject,output,config['selected_case_id'],required_observations=config.get('required_atoms',[]))
        frame_map = FrameMap(output/'video_frames.jsonl')
        frames, motion, indication, first_time = [], [], None, None
        walk_vector = carla.Vector3D(direction[0],direction[1],0)
        for index in range(config['frames']):
            if index == config['direction_frame']:
                pose = pose_direction(carla,officer,command,float(config.get('pose_pitch_delta_deg',0)))
            speed = walker_speed(command,responds,index,config['direction_frame'],float(config.get('walk_speed_mps',1.2)))
            subject.apply_control(carla.WalkerControl(direction=walk_vector,speed=speed,jump=False))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native pedestrian snapshot/frame mismatch')
            if first_time is None: first_time = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds-first_time
            cameras.wait(frame)
            trace = capture.capture(frame,time_s)
            if trace.get('frame') != frame or trace.get('time_s') != time_s:
                raise ValueError('Original pedestrian trace/frame join differs')
            frame_map.append(frame,time_s)
            velocity = subject.get_velocity()
            motion.append({'frame':frame,'time_s':time_s,'subject_id':str(subject.id),
                'speed_mps':math.hypot(velocity.x,velocity.y),
                'position_m':[subject.get_location().x,subject.get_location().y,subject.get_location().z]})
            if index == config['direction_frame']:
                indication = {'frame':frame,'officer_id':str(officer.id),'subject_id':str(subject.id),
                    'recipient_id':str(subject.id),'command':command,
                    'exact_direction_text':('Wait at the marked sidewalk location until released' if command=='stop'
                                           else 'You may proceed across the marked crosswalk now'),
                    'wait_location_source':'original crosswalk and sidewalk waypoint readback',
                    'communication_modality':'visual','communication_source':'original four-view video and walker arm pose',
                    'opportunity_source':'original four-view video; independent sightline review required',
                    'actual_perception':None,'indication_source':'original four-view video and walker arm pose',
                    'pose':pose}
            frames.append(frame)
        cameras.verify(frames)
        if indication is None:
            raise ValueError('No timed officer indication')
        (output/'officer_context.json').write_text(json.dumps({'actor_role':'pedestrian','officer_role':'police_officer',
            'officer_id':str(officer.id),'subject_id':str(subject.id),
            'duty_source':'scenario officer role assignment; independent authority review required',
            'lawfulness_source':'original indication and independent legal review required',
            'legal_conclusion':None,'willfulness_conclusion':None},indent=2)+'\n')
        (output/'officer_direction.json').write_text(json.dumps(indication,indent=2)+'\n')
        (output/'subject_motion.json').write_text(json.dumps({'frames':motion},indent=2)+'\n')
        (output/'subject_motion_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in motion))
        failed = False
    finally:
        if frame_map: frame_map.close()
        if capture: capture.close(confirmed=not failed)
        if cameras: cameras.close()
        for sink in sinks.values(): sink.close()
        for actor in reversed(actors): actor.destroy()
        world.apply_settings(settings_before)
        current = world.get_settings()
        if current.synchronous_mode != settings_before.synchronous_mode or current.fixed_delta_seconds != settings_before.fixed_delta_seconds:
            raise ValueError('Native pedestrian world-settings restore readback differs')
    (output/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'native',
        'diagnostic_fixture':False,'original_frames':len(frames)})+'\n')
    seal_capture(output,frames=len(frames),restoration={'restored':True},errors=[],
        encoder_exit_codes={name:0 for name in CAMERAS},context={'native_map_name':world.get_map().name,
        'crosswalk_start':[first.x,first.y,first.z],'crosswalk_end':[last.x,last.y,last.z],
        'sidewalk_start':[sidewalk_start.transform.location.x,sidewalk_start.transform.location.y],
        'sidewalk_end':[sidewalk_end.transform.location.x,sidewalk_end.transform.location.y]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args = parser.parse_args()
    if args.check:
        check_config(json.loads(Path('config.json').read_text()))
    else:
        if not args.output_dir: parser.error('--output-dir required')
        run(args.output_dir,args.host,args.port)

if __name__ == '__main__': main()
