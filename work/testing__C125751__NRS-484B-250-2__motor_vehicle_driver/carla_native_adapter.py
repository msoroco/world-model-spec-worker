"""CARLA-facing adapter for source-gated C125751 original acquisition.

The reviewed survey must supply actor transforms, camera mounts and exact
control schedules. This adapter refuses absent sources and does not choose a
legal or desired physical outcome. The caller owns client/world restoration.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from queue import Empty, Queue

from native_capture import CAMERAS


class CarlaNativeAdapter:
    def __init__(self, client, carla, survey):
        self.client, self.carla, self.survey = client, carla, survey
        self.world = client.get_world()
        self.sensors = {}
        self.queues = {}
        self.output = None

    def verify_map(self, survey, raw_map):
        if survey != self.survey:
            raise ValueError('reviewed crossing survey differs')
        actual = self.world.get_map().to_opendrive().encode()
        if hashlib.sha256(actual).hexdigest() != hashlib.sha256(raw_map).hexdigest():
            raise ValueError('CARLA OpenDRIVE readback differs')
        settings = self.world.get_settings()
        if not settings.synchronous_mode or not math.isclose(settings.fixed_delta_seconds,.05,abs_tol=1e-6):
            raise ValueError('CARLA synchronous 20 Hz world required')
        if not isinstance(survey.get('actor_sources'),dict) or set(survey['actor_sources']) != {'ego','other'}:
            raise ValueError('reviewed actor spawn sources required')
        if not isinstance(survey.get('camera_sources'),dict) or set(survey['camera_sources']) != set(CAMERAS):
            raise ValueError('reviewed four-camera mount sources required')
        controls = survey.get('control_schedules')
        if not isinstance(controls,dict) or set(controls) != {'ego','other'}:
            raise ValueError('reviewed actor control schedules required')
        if type(survey.get('governing_signal_actor_id')) is not int:
            raise ValueError('reviewed governing signal actor ID required')

    def _transform(self, source):
        if not isinstance(source,dict) or set(source) != {'location','rotation'}:
            raise ValueError('reviewed CARLA transform required')
        xyz, angles = source['location'], source['rotation']
        if (not isinstance(xyz,list) or len(xyz)!=3 or
                not isinstance(angles,list) or len(angles)!=3 or
                any(type(value) not in (int,float) or not math.isfinite(value)
                    for value in xyz+angles)):
            raise ValueError('finite reviewed CARLA transform required')
        return self.carla.Transform(self.carla.Location(*xyz),self.carla.Rotation(*angles))

    def spawn_actors(self, survey, case_id):
        spawned = {}
        try:
            for name in ('ego','other'):
                source = survey['actor_sources'][name]
                blueprint = self.world.get_blueprint_library().find(source['blueprint_id'])
                actor = self.world.try_spawn_actor(blueprint,self._transform(source['transform']))
                if actor is None:
                    raise ValueError('reviewed crossing actor spawn failed: '+name)
                spawned[name] = actor
            return spawned
        except Exception:
            for actor in reversed(list(spawned.values())):
                actor.destroy()
            raise

    def configure_cameras(self, ego, channels, *, fps, output):
        if tuple(channels) != CAMERAS or fps != 20:
            raise ValueError('original four-camera 20 Hz profile differs')
        self.output = Path(output)
        try:
            for name in CAMERAS:
                source = self.survey['camera_sources'][name]
                blueprint = self.world.get_blueprint_library().find('sensor.camera.rgb')
                for key in ('image_size_x','image_size_y','fov'):
                    blueprint.set_attribute(key,str(source[key]))
                blueprint.set_attribute('sensor_tick','0.05')
                sensor = self.world.spawn_actor(blueprint,self._transform(source['mount']),attach_to=ego)
                queue = Queue()
                sensor.listen(queue.put)
                self.sensors[name],self.queues[name] = sensor,queue
        except Exception:
            self.close_cameras()
            raise

    def request_controls(self, handles, case_id, index):
        suffix = case_id.rsplit('__',1)[-1]
        if suffix not in ('precedence','advance','timing_below','timing_inside','timing_above'):
            raise ValueError('foreign exact control case')
        for name in ('ego','other'):
            schedule = self.survey['control_schedules'][name].get(suffix)
            if not isinstance(schedule,list):
                raise ValueError('reviewed exact actor control schedule missing')
            rows = [row for row in schedule if row['start_frame']<=index<=row['end_frame']]
            if len(rows)!=1:
                raise ValueError('reviewed control schedule gap or overlap')
            row=rows[0]
            values = [row.get(key) for key in ('throttle','brake','steer')]
            if (any(type(value) not in (int,float) or not math.isfinite(value) for value in values) or
                    not 0<=values[0]<=1 or not 0<=values[1]<=1 or not -1<=values[2]<=1):
                raise ValueError('reviewed actor control outside CARLA range')
            handles[name].apply_control(self.carla.VehicleControl(
                throttle=values[0],brake=values[1],steer=values[2]))

    def tick(self):
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if frame != snapshot.frame:
            raise ValueError('CARLA tick/snapshot frame differs')
        return frame,snapshot.timestamp.elapsed_seconds

    def actor_snapshot(self, actor, frame):
        location = actor.get_location()
        waypoint = self.world.get_map().get_waypoint(location,project_to_road=False)
        if waypoint is None:
            raise ValueError('original actor road readback missing')
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        return {'id':actor.id,'road_id':waypoint.road_id,
                'body_vertices_xy_m':[[point.x,point.y] for point in vertices]}

    def signal_readback(self, survey, frame):
        signal = self.world.get_actor(survey['governing_signal_actor_id'])
        if signal is None:
            raise ValueError('original governing signal actor missing')
        state = str(signal.get_state()).split('.')[-1].lower()
        if state not in ('red','yellow','green','flashing','inoperative'):
            raise ValueError('original governing signal state unsupported')
        return state

    def camera_frame(self, name, frame):
        try:
            image = self.queues[name].get(timeout=10)
        except Empty as error:
            raise ValueError('original camera frame timeout') from error
        if image.frame != frame:
            raise ValueError('original camera callback frame differs')
        relative = Path('media')/name/f'{frame}.png'
        path = self.output/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        image.save_to_disk(str(path))
        return {'channel':name,'frame':frame,'source_path':str(relative),
                'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def close_cameras(self):
        for name in reversed(CAMERAS):
            sensor = self.sensors.pop(name,None)
            if sensor is not None:
                try:
                    sensor.stop()
                finally:
                    sensor.destroy()
        self.queues.clear()

    def emergency_stop(self, actor):
        actor.apply_control(self.carla.VehicleControl(throttle=0,brake=1,steer=0))

    def destroy(self, actor):
        actor.destroy()
